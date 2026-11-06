"""Leitura do CIC-IDS2017 corrigido (Engelen et al.) no formato da leitura original."""

import pandas as pd
import pytest

from nids import schema
from nids.data.improved import load_improved
from nids.data.load import RawFormatError

# Cabeçalho dos CSVs de https://intrusion-detection.distrinet-research.be/CNS2022/
IMPROVED_HEADER = [
    "id", "Flow ID", "Src IP", "Src Port", "Dst IP", "Dst Port", "Protocol", "Timestamp",
    "Flow Duration", "Total Fwd Packet", "Total Bwd packets", "Total Length of Fwd Packet",
    "Total Length of Bwd Packet", "Fwd Packet Length Max", "Fwd Packet Length Min",
    "Fwd Packet Length Mean", "Fwd Packet Length Std", "Bwd Packet Length Max",
    "Bwd Packet Length Min", "Bwd Packet Length Mean", "Bwd Packet Length Std", "Flow Bytes/s",
    "Flow Packets/s", "Flow IAT Mean", "Flow IAT Std", "Flow IAT Max", "Flow IAT Min",
    "Fwd IAT Total", "Fwd IAT Mean", "Fwd IAT Std", "Fwd IAT Max", "Fwd IAT Min",
    "Bwd IAT Total", "Bwd IAT Mean", "Bwd IAT Std", "Bwd IAT Max", "Bwd IAT Min",
    "Fwd PSH Flags", "Bwd PSH Flags", "Fwd URG Flags", "Bwd URG Flags", "Fwd RST Flags",
    "Bwd RST Flags", "Fwd Header Length", "Bwd Header Length", "Fwd Packets/s",
    "Bwd Packets/s", "Packet Length Min", "Packet Length Max", "Packet Length Mean",
    "Packet Length Std", "Packet Length Variance", "FIN Flag Count", "SYN Flag Count",
    "RST Flag Count", "PSH Flag Count", "ACK Flag Count", "URG Flag Count", "CWR Flag Count",
    "ECE Flag Count", "Down/Up Ratio", "Average Packet Size", "Fwd Segment Size Avg",
    "Bwd Segment Size Avg", "Fwd Bytes/Bulk Avg", "Fwd Packet/Bulk Avg", "Fwd Bulk Rate Avg",
    "Bwd Bytes/Bulk Avg", "Bwd Packet/Bulk Avg", "Bwd Bulk Rate Avg", "Subflow Fwd Packets",
    "Subflow Fwd Bytes", "Subflow Bwd Packets", "Subflow Bwd Bytes", "FWD Init Win Bytes",
    "Bwd Init Win Bytes", "Fwd Act Data Pkts", "Fwd Seg Size Min", "Active Mean",
    "Active Std", "Active Max", "Active Min", "Idle Mean", "Idle Std", "Idle Max", "Idle Min",
    "ICMP Code", "ICMP Type", "Total TCP Flow Time", "Label", "Attempted Category",
]  # fmt: skip

TEXT = {"Flow ID", "Src IP", "Dst IP", "Timestamp", "Label"}


def write_improved_csv(path, *overrides: dict):
    """Um fluxo por dicionário, com as colunas que diferem do fluxo normal padrão."""
    rows = []
    for i, override in enumerate(overrides):
        row = dict.fromkeys([c for c in IMPROVED_HEADER if c not in TEXT], 1)
        row |= {
            "id": i + 1,
            "Flow ID": f"192.168.10.5-192.168.10.50-{40000 + i}-80-6",
            "Src IP": "192.168.10.5",
            "Src Port": 40000 + i,
            "Dst IP": "192.168.10.50",
            "Timestamp": f"2017-07-03 12:{i:02d}:00.250000",
            "Flow Duration": 1000 + i,
            "Label": "BENIGN",
            "Attempted Category": -1,
        }
        rows.append(row | override)
    pd.DataFrame(rows, columns=IMPROVED_HEADER).to_csv(path, index=False)
    return path


def test_le_o_formato_corrigido_como_a_leitura_original(tmp_path):
    write_improved_csv(
        tmp_path / "monday.csv",
        {
            "Timestamp": "2017-07-03 12:30:15.500000",
            "FWD Init Win Bytes": 8192,
            "Total Fwd Packet": 3,
        },
        {"Label": "DoS Hulk - Attempted", "Attempted Category": 0},
        {"Label": "Botnet"},
        {"Label": "Infiltration - Portscan"},
        {"Label": "Web Attack - XSS"},
    )

    df = load_improved(tmp_path)

    assert list(df.columns) == [schema.ROW_ID, schema.DAY, *schema.RAW_COLUMNS]
    assert (df[schema.DAY] == "monday").all()
    # Tentativas sem conteúdo malicioso viram normais, como recomendam os autores
    assert df[schema.LABEL].tolist() == ["BENIGN", "BENIGN", "Bot", "PortScan", "Web Attack - XSS"]
    # Horário em UTC no arquivo; a captura foi em UTC-3, o horário da agenda dos ataques
    assert df[schema.TIMESTAMP].iloc[0] == "03/07/2017 09:30:15"
    # Atributos que mudaram de nome chegam pelo nome do conjunto original
    assert df["init_win_bytes_forward"].iloc[0] == 8192
    assert df["total_fwd_packets"].iloc[0] == 3


def test_rotulo_desconhecido_e_recusado(tmp_path):
    write_improved_csv(tmp_path / "monday.csv", {"Label": "Ataque Novo"})

    with pytest.raises(RawFormatError, match="Ataque Novo"):
        load_improved(tmp_path)
