"""O que o painel mostra, calculado em SQL no banco do replay: no fim do teste são quase um milhão
de vereditos, e o painel relê tudo a cada poucos segundos."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

from nids.schema import FAMILIES

VERDICTS = ["attack", "suspicious", "benign"]
ALERT = "verdict != 'benign'"
ATTACK = "family != 'BENIGN'"


def totals(db: Path) -> dict:
    """Fluxos vistos, alertas, ataques detectados e alarmes falsos até agora."""
    query = f"""
        SELECT COUNT(*), SUM({ALERT}), SUM({ATTACK}), SUM({ATTACK} AND {ALERT}),
               SUM(NOT {ATTACK} AND {ALERT}), SUM(NOT {ATTACK})
        FROM verdicts
    """
    with closing(_connect(db)) as conn:
        # Num banco ainda vazio, as somas vêm como NULL
        row = [value or 0 for value in conn.execute(query).fetchone()]
    flows, alerts, attacks, detected, false_alarms, benign = row
    return {
        "flows": flows,
        "alerts": alerts,
        "attacks": attacks,
        "detected": detected,
        "false_alarms": false_alarms,
        # No começo do replay ainda não há ataques (nem normais) para dividir
        "recall": detected / attacks if attacks else None,
        "fpr": false_alarms / benign if benign else None,
    }


def by_family(db: Path) -> pd.DataFrame:
    """Vereditos por família verdadeira. alert_rate é a revocação nos ataques e a taxa de
    alarmes falsos nos normais."""
    query = "SELECT family, verdict, COUNT(*) AS n FROM verdicts GROUP BY family, verdict"
    with closing(_connect(db)) as conn:
        counts = pd.read_sql(query, conn)
    table = counts.pivot(index="family", columns="verdict", values="n")
    table = table.reindex(columns=VERDICTS, fill_value=0).fillna(0).astype(int)
    table = table.reindex([f for f in FAMILIES if f in table.index])
    table["alert_rate"] = (table["attack"] + table["suspicious"]) / table.sum(axis=1)
    return table


def per_minute(db: Path) -> pd.DataFrame:
    """Alertas de cada veredito e ataques reais em cada minuto da captura."""
    query = f"""
        SELECT timestamp, SUM(verdict = 'attack') AS attack,
               SUM(verdict = 'suspicious') AS suspicious, SUM({ATTACK}) AS true_attacks
        FROM verdicts GROUP BY timestamp ORDER BY timestamp
    """
    with closing(_connect(db)) as conn:
        return pd.read_sql(query, conn, index_col="timestamp", parse_dates=["timestamp"])


def recent_alerts(db: Path, n: int = 20) -> pd.DataFrame:
    """Os n alertas mais recentes, do mais novo ao mais antigo. Acerto: o fluxo era ataque."""
    query = f"""
        SELECT timestamp, source_ip, destination_ip, destination_port, verdict,
               predicted_family, family, {ATTACK} AS correct
        FROM verdicts WHERE {ALERT} ORDER BY rowid DESC LIMIT ?
    """
    with closing(_connect(db)) as conn:
        alerts = pd.read_sql(query, conn, params=(n,), parse_dates=["timestamp"])
    return alerts.astype({"correct": bool})


def _connect(db: Path) -> sqlite3.Connection:
    # Só leitura: o replay pode estar escrevendo no mesmo banco
    return sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
