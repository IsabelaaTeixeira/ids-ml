"""Leitura do CSE-CIC-IDS2018 corrigido (Engelen et al.), para testar os modelos em outra rede.

Os CSVs (CSECICIDS2018_improved.zip, 36 GB descompactados, 63 milhões de fluxos) saíram do mesmo
extrator consertado do CIC-IDS2017 corrigido e têm o mesmo cabeçalho. read_chunks lê direto do
zip, em pedaços, e entrega os 60 atributos com a família no vocabulário do 2017 e a mesma limpeza
por fluxo do pipeline. Não há remoção de duplicatas: ela serve para separar treino e teste, e aqui
o treino é outro conjunto (ADR 0011).
"""

import logging
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from nids import schema
from nids.data.clean import (
    clip_negative_times,
    drop_header_overflow,
    drop_missing_values,
    fill_instant_rates,
)
from nids.data.improved import ATTEMPTED, column_names, read_options
from nids.data.load import RawFormatError

# Rótulos do 2018 que o 2017 escreve de outro jeito
LABELS = {
    "Botnet Ares": "Bot",
    "DDoS-HOIC": "DDoS",
    "DDoS-LOIC-HTTP": "DDoS",
    "DDoS-LOIC-UDP": "DDoS",
    "FTP-BruteForce": "FTP-Patator",
    "SSH-BruteForce": "SSH-Patator",
    "Infiltration - Communication Victim Attacker": "Infiltration",
    "Infiltration - Dropbox Download": "Infiltration",
    # A varredura feita pela máquina invadida, como no 2017 corrigido (ADR 0010)
    "Infiltration - NMAP Portscan": "PortScan",
    "Web Attack - SQL": "Web Attack - Sql Injection",
}

KEEP = [*schema.FEATURES, schema.LABEL]

log = logging.getLogger(__name__)
CLEANING = (clip_negative_times, fill_instant_rates, drop_header_overflow, drop_missing_values)


def date_from_filename(name: str) -> str:
    """'Friday-02-03-2018.csv' -> '2018-03-02'."""
    try:
        return pd.to_datetime(Path(name).stem.split("-", 1)[1], format="%d-%m-%Y").strftime(
            "%Y-%m-%d"
        )
    except (IndexError, ValueError) as error:
        raise RawFormatError(f"{name}: não dá para saber a data pelo nome do arquivo") from error


def prepare(chunk: pd.DataFrame, date: str) -> pd.DataFrame:
    """Rótulos no vocabulário do 2017, família e a limpeza por fluxo do pipeline."""
    # Os autores recomendam tratar os fluxos "Attempted" como normais
    labels = chunk[schema.LABEL].mask(chunk.pop(ATTEMPTED) != -1, schema.BENIGN).replace(LABELS)
    keys = {label: schema.normalize_label(label) for label in labels.unique()}
    unknown = sorted(label for label, key in keys.items() if key not in schema.LABELS)
    if unknown:
        raise RawFormatError(f"rótulos desconhecidos no 2018: {unknown}")
    canonical = labels.map({label: schema.LABELS[key][0] for label, key in keys.items()})
    df = chunk.assign(**{schema.LABEL: canonical, schema.FAMILY: canonical.map(schema.FAMILY_OF)})
    for step in CLEANING:
        df, _ = step(df)
    df.insert(0, "date", date)
    return df[["date", schema.LABEL, schema.FAMILY, *schema.FEATURES]].reset_index(drop=True)


def read_chunks(zip_path: Path, chunksize: int = 1_000_000) -> Iterator[pd.DataFrame]:
    """Os fluxos de cada CSV do zip, em ordem de data, em pedaços de até chunksize linhas."""
    with zipfile.ZipFile(zip_path) as zf:
        for name in sorted(zf.namelist(), key=date_from_filename):
            date = date_from_filename(name)
            log.info("Lendo %s", name)
            with zf.open(name) as file:
                header = pd.read_csv(file, nrows=0).columns
            names = column_names(header, KEEP)
            with zf.open(name) as file:
                for chunk in pd.read_csv(file, chunksize=chunksize, **read_options(header, KEEP)):
                    yield prepare(chunk.rename(columns=names), date)
