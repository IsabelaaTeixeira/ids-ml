"""Regras de limpeza (seção 5.3 da arquitetura).

Cada regra recebe um DataFrame e devolve o DataFrame resultante mais um dicionário
com o que fez. `clean` aplica todas em ordem e monta o relatório de qualidade.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from nids import schema

Step = Callable[..., tuple[pd.DataFrame, dict[str, Any]]]


def drop_empty_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Remove linhas sem rótulo (alguns CSVs têm muitas linhas só com vírgulas)."""
    return df[df[schema.LABEL].notna()], {}


def normalize_labels(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Converte os rótulos para a forma canônica e adiciona a família de ataque."""
    raw_labels = df[schema.LABEL].unique()
    keys = {raw: schema.normalize_label(raw) for raw in raw_labels}
    unknown = sorted(raw for raw, key in keys.items() if key not in schema.LABELS)
    if unknown:
        raise ValueError(f"Rótulos desconhecidos: {unknown}")

    canonical = {raw: schema.LABELS[key][0] for raw, key in keys.items()}
    labels = df[schema.LABEL].map(canonical)
    df = df.assign(
        **{
            schema.LABEL: pd.Categorical(labels, categories=schema.LABEL_NAMES),
            schema.FAMILY: pd.Categorical(labels.map(schema.FAMILY_OF), categories=schema.FAMILIES),
        }
    )
    renamed = {raw: new for raw, new in canonical.items() if raw != new}
    return df, {"renamed": renamed}


def drop_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Remove as colunas de schema.DROPPED, registrando quantos valores distintos tinham."""
    details = {
        col: {"reason": reason, "distinct_values": int(df[col].nunique())}
        for col, reason in schema.DROPPED.items()
    }
    return df.drop(columns=list(schema.DROPPED)), details


def parse_timestamps(
    df: pd.DataFrame, first_capture_hour: int
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Converte o Timestamp para datetime e corrige o relógio de 12h sem AM/PM.

    Os arquivos misturam 'dd/mm/aaaa hh:mm:ss' e 'd/m/aaaa h:mm', e todos usam relógio
    de 12h. A captura começa em first_capture_hour, então horas anteriores são da tarde.
    Linhas sem data válida ou com data diferente do dia do arquivo são removidas.
    """
    text = df[schema.TIMESTAMP].str.strip()
    with_seconds = pd.to_datetime(text, format="%d/%m/%Y %H:%M:%S", errors="coerce")
    without_seconds = pd.to_datetime(text, format="%d/%m/%Y %H:%M", errors="coerce")
    timestamps = with_seconds.fillna(without_seconds)

    afternoon = timestamps.dt.hour < first_capture_hour
    timestamps = timestamps.mask(afternoon, timestamps + pd.Timedelta(hours=12))

    unparsed = timestamps.isna()
    expected_date = pd.to_datetime(df[schema.DAY].astype(str).map(schema.DAY_DATES))
    wrong_date = ~unparsed & (timestamps.dt.normalize() != expected_date)

    details = {
        "with_seconds": int(with_seconds.notna().sum()),
        "without_seconds": int((with_seconds.isna() & without_seconds.notna()).sum()),
        "shifted_12h": int(afternoon.sum()),
        "unparsed": int(unparsed.sum()),
        "wrong_date": int(wrong_date.sum()),
    }
    df = df.assign(**{schema.TIMESTAMP: timestamps})
    return df[~unparsed & ~wrong_date], details


def clip_negative_times(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """ADR 0006: tempos negativos (de −14 a −1 µs, imprecisão do relógio da captura) viram 0."""
    clipped = {c: int(n) for c in schema.TIME_FEATURES if (n := (df[c] < 0).sum())}
    df = df.assign(**{c: df[c].clip(lower=0) for c in clipped})
    return df, {"clipped": clipped}


def fill_instant_rates(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """ADR 0006: fluxos de duração zero ficam, com as taxas por segundo iguais a 0.

    É a convenção que o próprio CICFlowMeter já usa em fwd_packets_s e bwd_packets_s.
    """
    instant = df["flow_duration"] == 0
    df = df.assign(**{c: df[c].mask(instant, 0) for c in schema.RATE_FEATURES})
    return df, {"instant_flows": int(instant.sum())}


def drop_header_overflow(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """ADR 0006: tamanho de cabeçalho negativo só pode ser overflow de inteiro; a linha sai."""
    overflow = (df[schema.HEADER_FEATURES] < 0).any(axis=1)
    return df[~overflow], {}


def drop_missing_values(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Troca ±inf por NaN e remove as linhas com algum valor faltando nas features."""
    infinite = {c: int(n) for c in schema.FEATURES if (n := np.isinf(df[c]).sum())}
    df = df.assign(**{c: df[c].replace([np.inf, -np.inf], np.nan) for c in infinite})
    missing = {c: int(n) for c in schema.FEATURES if (n := df[c].isna().sum())}
    return df.dropna(subset=schema.FEATURES), {"infinite": infinite, "missing": missing}


def drop_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Remove duplicatas antes do split, para a mesma linha não cair no treino e no teste.

    Duplicata exata (mesmas features e rótulo): fica a primeira no tempo.
    Duplicata conflitante (mesmas features, rótulos diferentes): todas saem,
    porque não dá para saber qual rótulo está certo.
    """
    df = df.sort_values([schema.TIMESTAMP, schema.ROW_ID])
    exact = df.duplicated(subset=[*schema.FEATURES, schema.LABEL], keep="first")
    exact_by_label = _counts(df.loc[exact, schema.LABEL])
    df = df[~exact]
    conflicting = df.duplicated(subset=schema.FEATURES, keep=False)
    details = {
        "exact": int(exact.sum()),
        "exact_by_label": exact_by_label,
        "conflicting": int(conflicting.sum()),
        "conflicting_by_label": _counts(df.loc[conflicting, schema.LABEL]),
    }
    return df[~conflicting], details


def report_constant_features(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Não altera nada: lista features com um único valor, candidatas a schema.DROPPED."""
    constant = [c for c in schema.FEATURES if df[c].nunique() <= 1]
    return df, {"constant_features": constant}


def report_negative_values(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Não altera nada: conta valores negativos por feature, para decidir o tratamento na EDA."""
    negatives = {c: int(n) for c in schema.FEATURES if (n := (df[c] < 0).sum())}
    return df, {"negative_values": negatives}


@dataclass
class QualityReport:
    rows_raw: int
    steps: list[dict[str, Any]] = field(default_factory=list)

    def run(self, step: Step, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        rows_before = len(df)
        df, details = step(df, **kwargs)
        self.steps.append(
            {
                "step": step.__name__,
                "rows_before": rows_before,
                "rows_after": len(df),
                "removed": rows_before - len(df),
                "details": details,
            }
        )
        return df

    def to_dict(self, clean_df: pd.DataFrame) -> dict[str, Any]:
        return {
            "rows_raw": self.rows_raw,
            "rows_clean": len(clean_df),
            "steps": self.steps,
            "labels": _counts(clean_df[schema.LABEL]),
            "families": _counts(clean_df[schema.FAMILY]),
        }


def clean(raw: pd.DataFrame, first_capture_hour: int = 8) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Aplica todas as regras e devolve o dataset limpo e o relatório de qualidade."""
    report = QualityReport(rows_raw=len(raw))
    df = report.run(drop_empty_rows, raw)
    df = report.run(normalize_labels, df)
    df = report.run(drop_columns, df)
    df = report.run(parse_timestamps, df, first_capture_hour=first_capture_hour)
    df = report.run(clip_negative_times, df)
    df = report.run(fill_instant_rates, df)
    df = report.run(drop_header_overflow, df)
    df = report.run(drop_missing_values, df)
    df = report.run(drop_duplicates, df)
    df = report.run(report_constant_features, df)
    df = report.run(report_negative_values, df)
    df = df[schema.CLEAN_COLUMNS].astype({"source_port": "Int32"}).reset_index(drop=True)
    return df, report.to_dict(df)


def _counts(values: pd.Series) -> dict[str, int]:
    return {str(k): int(n) for k, n in values.value_counts().items() if n}
