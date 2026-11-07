"""Bancos do replay feitos à mão: a tabela verdicts no formato que nids.demo.replay grava."""

import sqlite3
from contextlib import closing

import pandas as pd
import pytest

# (minuto, família verdadeira, veredito, família prevista, atributos que explicam o alerta)
ROWS = [
    ("09:00", "BENIGN", "benign", None, ""),
    ("09:00", "BENIGN", "suspicious", None, "idle_mean, flow_iat_max"),  # alarme falso
    ("09:00", "PortScan", "attack", "PortScan", "destination_port, flow_duration"),  # acerto
    ("09:01", "PortScan", "benign", None, ""),  # ataque perdido
    ("09:01", "Infiltration", "suspicious", None, "total_fwd_packets"),  # acerto pelo detector
    ("09:01", "BENIGN", "benign", None, ""),
]
COLUMNS = ["timestamp", "family", "verdict", "predicted_family", "explanation"]


@pytest.fixture
def verdicts_db(tmp_path):
    """Banco com os seis vereditos de ROWS, na ordem em que o replay os teria gravado."""
    rows = pd.DataFrame(ROWS, columns=COLUMNS)
    rows["timestamp"] = "2017-07-06 " + rows["timestamp"] + ":00"
    rows["source_ip"] = [f"10.0.0.{i}" for i in range(1, len(rows) + 1)]
    rows["destination_ip"] = "192.168.10.50"
    rows["destination_port"] = 80
    rows["attack_probability"] = 0.5
    rows["anomaly_score"] = 0.1
    db = tmp_path / "replay.db"
    with closing(sqlite3.connect(db)) as conn:
        rows.to_sql("verdicts", conn, index=False)
    return db
