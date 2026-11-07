"""Leitura do CIC-IDS2017 corrigido por Engelen et al. no formato da leitura original.

Os CSVs (https://intrusion-detection.distrinet-research.be/CNS2022/) vêm do extrator de fluxos
consertado, com outros nomes de colunas, horário em UTC e um rótulo "Attempted" para fluxos de
ataque sem conteúdo malicioso. load_improved entrega o mesmo formato de load_raw; daí em diante,
a limpeza e o resto do pipeline são os mesmos (ADR 0010).
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from nids import schema
from nids.data.load import TEXT_COLUMNS, RawFormatError

log = logging.getLogger(__name__)

# Nomes (já normalizados) que mudaram em relação ao conjunto original
RENAMED = {
    "src_ip": "source_ip",
    "src_port": "source_port",
    "dst_ip": "destination_ip",
    "dst_port": "destination_port",
    "total_fwd_packet": "total_fwd_packets",
    "total_bwd_packets": "total_backward_packets",
    "total_length_of_fwd_packet": "total_length_of_fwd_packets",
    "total_length_of_bwd_packet": "total_length_of_bwd_packets",
    "packet_length_min": "min_packet_length",
    "packet_length_max": "max_packet_length",
    "cwr_flag_count": "cwe_flag_count",
    "fwd_segment_size_avg": "avg_fwd_segment_size",
    "bwd_segment_size_avg": "avg_bwd_segment_size",
    "fwd_bytes_bulk_avg": "fwd_avg_bytes_bulk",
    "fwd_packet_bulk_avg": "fwd_avg_packets_bulk",
    "fwd_bulk_rate_avg": "fwd_avg_bulk_rate",
    "bwd_bytes_bulk_avg": "bwd_avg_bytes_bulk",
    "bwd_packet_bulk_avg": "bwd_avg_packets_bulk",
    "bwd_bulk_rate_avg": "bwd_avg_bulk_rate",
    "fwd_init_win_bytes": "init_win_bytes_forward",
    "bwd_init_win_bytes": "init_win_bytes_backward",
    "fwd_act_data_pkts": "act_data_pkt_fwd",
    "fwd_seg_size_min": "min_seg_size_forward",
}

# Rótulos que o original não tem. A varredura feita pela máquina invadida, na quinta, vira
# PortScan; o dia a separa da varredura externa de sexta.
LABELS = {"Botnet": "Bot", "Infiltration - Portscan": "PortScan"}

ATTEMPTED = "attempted_category"  # -1 nos fluxos que não são "Attempted"

# A captura foi no horário de verão do leste do Canadá (UTC-3), o da agenda oficial dos ataques
CAPTURE_OFFSET = pd.Timedelta(hours=-3)


def day_from_filename(path: Path) -> str:
    """'monday.csv' -> 'monday'."""
    day = path.stem.lower()
    if day not in schema.DAYS:
        raise RawFormatError(f"{path.name}: não dá para saber o dia pelo nome do arquivo")
    return day


def column_names(header, keep) -> dict[str, str]:
    """Colunas do cabeçalho corrigido que interessam, com o nome do conjunto original."""
    names = {c: RENAMED.get(schema.normalize_name(c), schema.normalize_name(c)) for c in header}
    return {c: n for c, n in names.items() if n in keep or n == ATTEMPTED}


def read_options(header, keep) -> dict:
    """usecols e dtype para o pd.read_csv, com os nomes de column_names."""
    wanted = column_names(header, keep)
    dtypes = {c: ("str" if n in TEXT_COLUMNS else "float32") for c, n in wanted.items()}
    return {"usecols": list(wanted), "dtype": dtypes}


def read_improved_csv(path: Path) -> pd.DataFrame:
    """Lê um CSV do conjunto corrigido e devolve as colunas e rótulos do conjunto original."""
    day = day_from_filename(path)
    header = pd.read_csv(path, nrows=0).columns
    names = column_names(header, schema.RAW_COLUMNS)
    df = pd.read_csv(path, **read_options(header, schema.RAW_COLUMNS)).rename(columns=names)

    # A cópia de Fwd Header Length do original não existe aqui; ela é descartada na limpeza
    df["fwd_header_length_1"] = df["fwd_header_length"]
    missing = sorted(set(schema.RAW_COLUMNS) - set(df.columns))
    if missing:
        raise RawFormatError(f"{path.name}: colunas faltando: {missing}")

    # Os autores recomendam tratar os fluxos "Attempted" como normais
    labels = df[schema.LABEL].replace(LABELS).mask(df.pop(ATTEMPTED) != -1, schema.BENIGN)
    unknown = sorted(
        {label for label in labels.unique() if schema.normalize_label(label) not in schema.LABELS}
    )
    if unknown:
        raise RawFormatError(f"{path.name}: rótulos desconhecidos: {unknown}")

    local = pd.to_datetime(df[schema.TIMESTAMP]) + CAPTURE_OFFSET
    df = df.assign(
        **{schema.LABEL: labels, schema.TIMESTAMP: local.dt.strftime("%d/%m/%Y %H:%M:%S")}
    )
    df = df[schema.RAW_COLUMNS]
    df.insert(0, schema.DAY, pd.Categorical([day] * len(df), categories=schema.DAYS, ordered=True))
    return df


def load_improved(raw_dir: Path) -> pd.DataFrame:
    """Lê os CSVs de raw_dir (monday.csv a friday.csv), na ordem dos dias, com row_id."""
    paths = sorted(raw_dir.glob("*.csv"), key=lambda p: schema.DAYS.index(day_from_filename(p)))
    if not paths:
        raise FileNotFoundError(f"Nenhum CSV em {raw_dir}")
    frames = []
    for path in paths:
        log.info("Lendo %s", path.name)
        frames.append(read_improved_csv(path))
    df = pd.concat(frames, ignore_index=True)
    df.insert(0, schema.ROW_ID, np.arange(len(df), dtype="int64"))
    return df
