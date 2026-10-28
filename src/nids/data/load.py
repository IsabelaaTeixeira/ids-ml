"""Leitura dos CSVs originais do CIC-IDS2017."""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from nids import schema

log = logging.getLogger(__name__)

# Os CSVs não são UTF-8: o rótulo "Web Attack – ..." usa um byte do cp1252.
# latin-1 nunca falha na leitura, e os rótulos são normalizados na limpeza.
ENCODING = "latin-1"

TEXT_COLUMNS = ["flow_id", "source_ip", "destination_ip", schema.TIMESTAMP, schema.LABEL]


class RawFormatError(ValueError):
    """O arquivo não está no formato esperado."""


def day_from_filename(path: Path) -> str:
    """'Tuesday-WorkingHours.pcap_ISCX.csv' -> 'tuesday'."""
    day = path.name.split("-", 1)[0].lower()
    if day not in schema.DAYS:
        raise RawFormatError(f"{path.name}: não dá para saber o dia pelo nome do arquivo")
    return day


def read_raw_csv(path: Path) -> pd.DataFrame:
    """Lê um CSV, confere o cabeçalho e devolve as colunas com nomes normalizados."""
    header = pd.read_csv(path, nrows=0, encoding=ENCODING).columns
    columns = [schema.normalize_name(c) for c in header]
    if columns != schema.RAW_COLUMNS:
        missing = sorted(set(schema.RAW_COLUMNS) - set(columns))
        extra = sorted(set(columns) - set(schema.RAW_COLUMNS))
        raise RawFormatError(
            f"{path.name}: cabeçalho inesperado. Faltando: {missing}. Sobrando: {extra}."
        )

    dtypes = {c: "float32" for c in schema.RAW_COLUMNS if c not in TEXT_COLUMNS}
    dtypes |= {c: "str" for c in TEXT_COLUMNS}
    df = pd.read_csv(path, header=0, names=schema.RAW_COLUMNS, dtype=dtypes, encoding=ENCODING)
    day = pd.Categorical([day_from_filename(path)] * len(df), categories=schema.DAYS, ordered=True)
    df.insert(0, schema.DAY, day)
    return df


def load_raw(raw_dir: Path) -> pd.DataFrame:
    """Lê todos os CSVs de raw_dir, na ordem dos dias, e numera as linhas com row_id."""
    paths = sorted(
        raw_dir.glob("*.csv"),
        key=lambda p: (schema.DAYS.index(day_from_filename(p)), p.name),
    )
    if not paths:
        raise FileNotFoundError(f"Nenhum CSV em {raw_dir}")

    frames = []
    for path in paths:
        log.info("Lendo %s", path.name)
        frames.append(read_raw_csv(path))
    df = pd.concat(frames, ignore_index=True)
    df.insert(0, schema.ROW_ID, np.arange(len(df), dtype="int64"))
    return df
