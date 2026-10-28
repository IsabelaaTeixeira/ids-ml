"""Fixtures compartilhadas: dados sintéticos no formato do CIC-IDS2017."""

import numpy as np
import pandas as pd
import pytest

from nids import schema

# Cabeçalho real dos CSVs (GeneratedLabelledFlows): espaços no início, maiúsculas,
# barras e "Fwd Header Length" repetida.
ORIGINAL_HEADER = [
    "Flow ID", " Source IP", " Source Port", " Destination IP", " Destination Port",
    " Protocol", " Timestamp", " Flow Duration", " Total Fwd Packets",
    " Total Backward Packets", "Total Length of Fwd Packets", " Total Length of Bwd Packets",
    " Fwd Packet Length Max", " Fwd Packet Length Min", " Fwd Packet Length Mean",
    " Fwd Packet Length Std", "Bwd Packet Length Max", " Bwd Packet Length Min",
    " Bwd Packet Length Mean", " Bwd Packet Length Std", "Flow Bytes/s", " Flow Packets/s",
    " Flow IAT Mean", " Flow IAT Std", " Flow IAT Max", " Flow IAT Min", "Fwd IAT Total",
    " Fwd IAT Mean", " Fwd IAT Std", " Fwd IAT Max", " Fwd IAT Min", "Bwd IAT Total",
    " Bwd IAT Mean", " Bwd IAT Std", " Bwd IAT Max", " Bwd IAT Min", "Fwd PSH Flags",
    " Bwd PSH Flags", " Fwd URG Flags", " Bwd URG Flags", " Fwd Header Length",
    " Bwd Header Length", "Fwd Packets/s", " Bwd Packets/s", " Min Packet Length",
    " Max Packet Length", " Packet Length Mean", " Packet Length Std",
    " Packet Length Variance", "FIN Flag Count", " SYN Flag Count", " RST Flag Count",
    " PSH Flag Count", " ACK Flag Count", " URG Flag Count", " CWE Flag Count",
    " ECE Flag Count", " Down/Up Ratio", " Average Packet Size", " Avg Fwd Segment Size",
    " Avg Bwd Segment Size", " Fwd Header Length", "Fwd Avg Bytes/Bulk",
    " Fwd Avg Packets/Bulk", " Fwd Avg Bulk Rate", " Bwd Avg Bytes/Bulk",
    " Bwd Avg Packets/Bulk", "Bwd Avg Bulk Rate", "Subflow Fwd Packets", " Subflow Fwd Bytes",
    " Subflow Bwd Packets", " Subflow Bwd Bytes", "Init_Win_bytes_forward",
    " Init_Win_bytes_backward", " act_data_pkt_fwd", " min_seg_size_forward", "Active Mean",
    " Active Std", " Active Max", " Active Min", "Idle Mean", " Idle Std", " Idle Max",
    " Idle Min", " Label",
]  # fmt: skip

TEXT_COLUMNS = {"flow_id", "source_ip", "destination_ip", schema.TIMESTAMP, schema.LABEL}
NUMERIC_COLUMNS = [c for c in schema.RAW_COLUMNS if c not in TEXT_COLUMNS]


def _raw_rows(overrides: tuple[dict, ...]) -> list[dict]:
    """Uma linha por dicionário. flow_duration muda a cada linha para não gerar duplicatas."""
    rows = []
    for i, override in enumerate(overrides):
        row = dict.fromkeys(NUMERIC_COLUMNS, 1.0)
        row |= dict.fromkeys([c for c in schema.DROPPED if c in NUMERIC_COLUMNS], 0.0)
        row |= {
            "flow_id": f"192.168.10.5-192.168.10.50-{40000 + i}-80-6",
            "source_ip": "192.168.10.5",
            "source_port": float(40000 + i),
            "destination_ip": "192.168.10.50",
            "timestamp": "03/07/2017 09:00:00",
            "flow_duration": float(i),
            "label": "BENIGN",
        }
        rows.append(row | override)
    return rows


@pytest.fixture
def raw_frame():
    """Fábrica de DataFrames no formato devolvido por `load_raw`, antes da limpeza.

    Cada argumento é um dicionário com as colunas que diferem da linha padrão
    (tráfego normal de segunda às 9h). A chave "day" muda o dia do arquivo.
    """

    def make(*overrides: dict) -> pd.DataFrame:
        days = [o.get(schema.DAY, "monday") for o in overrides]
        rows = [{k: v for k, v in row.items() if k != schema.DAY} for row in _raw_rows(overrides)]
        df = pd.DataFrame(rows, columns=schema.RAW_COLUMNS)
        df[NUMERIC_COLUMNS] = df[NUMERIC_COLUMNS].astype("float32")
        df.insert(0, schema.DAY, pd.Categorical(days, categories=schema.DAYS, ordered=True))
        df.insert(0, schema.ROW_ID, np.arange(len(df), dtype="int64"))
        return df

    return make


@pytest.fixture
def write_raw_csv():
    """Grava um CSV como os originais: cabeçalho real e encoding cp1252.

    Os valores são escritos como vieram, então dá para testar "Infinity" e linhas vazias.
    """

    def write(path, *overrides: dict):
        df = pd.DataFrame(_raw_rows(overrides), columns=schema.RAW_COLUMNS)
        df.columns = ORIGINAL_HEADER
        df.to_csv(path, index=False, encoding="cp1252")
        return path

    return write


@pytest.fixture
def make_flows():
    """Fábrica de DataFrames no formato do dataset limpo (data/interim/flows.parquet).

    `groups` diz quantas linhas criar para cada (dia, rótulo canônico). As linhas saem
    fora da ordem temporal de propósito, para os testes não dependerem da ordem.
    """

    def make(groups: dict[tuple[str, str], int], seed: int = 0) -> pd.DataFrame:
        rng = np.random.default_rng(seed)
        frames = []
        for (day, label), n in groups.items():
            start = pd.Timestamp(schema.DAY_DATES[day]) + pd.Timedelta(hours=9)
            minutes = pd.to_timedelta(rng.permutation(n), unit="min")
            frames.append(
                pd.DataFrame(
                    {schema.DAY: day, schema.TIMESTAMP: start + minutes, schema.LABEL: label}
                )
            )
        df = pd.concat(frames, ignore_index=True)

        features = rng.random((len(df), len(schema.FEATURES)), dtype=np.float32)
        df = pd.concat([df, pd.DataFrame(features, columns=schema.FEATURES)], axis=1)
        df[schema.ROW_ID] = np.arange(len(df), dtype="int64")
        df["source_ip"] = "192.168.10.5"
        df["source_port"] = pd.array(40000 + np.arange(len(df)), dtype="Int32")
        df["destination_ip"] = "192.168.10.50"
        df[schema.DAY] = pd.Categorical(df[schema.DAY], categories=schema.DAYS, ordered=True)
        df[schema.FAMILY] = pd.Categorical(
            df[schema.LABEL].map(schema.FAMILY_OF), categories=schema.FAMILIES
        )
        df[schema.LABEL] = pd.Categorical(df[schema.LABEL], categories=schema.LABEL_NAMES)
        return df[schema.CLEAN_COLUMNS]

    return make
