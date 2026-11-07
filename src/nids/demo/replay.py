"""Replay do teste pela API (etapa 5): os fluxos vão em ordem cronológica e cada veredito é
gravado num SQLite ao lado do rótulo verdadeiro, para o painel ler enquanto o replay roda.

O replay só conversa com a API por HTTP, sem importar o Predictor: a demonstração exercita o
serviço de verdade.
"""

import logging
import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

import httpx2
import pandas as pd

from nids import schema

# Ficam no banco, mas nunca vão para a API: identificam o fluxo, não o descrevem
KEPT = [schema.TIMESTAMP, "source_ip", "destination_ip", "destination_port", schema.FAMILY]

# Maior pausa reproduzida: a noite entre quinta e sexta não vira horas de espera
MAX_GAP = pd.Timedelta(minutes=5)

ROLES = {"classifier": "classificador", "detector": "detector"}

log = logging.getLogger(__name__)

TABLE = """
CREATE TABLE verdicts (
    timestamp TEXT, source_ip TEXT, destination_ip TEXT, destination_port INTEGER,
    family TEXT, verdict TEXT, predicted_family TEXT, attack_probability REAL, anomaly_score REAL,
    explanation TEXT
)
"""


def replay(
    flows: pd.DataFrame,
    client: httpx2.Client,
    db: Path,
    protocol: str,
    speed: float = 60,
    batch_size: int = 1000,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Manda os fluxos (o teste de `protocol`) à API no ritmo da captura acelerado `speed` vezes
    (60: um minuto de captura por segundo) e grava os vereditos em `db`, que começa vazio."""
    # O teste de um protocolo só é inédito para os modelos treinados nele: o XGBoost do P1,
    # por exemplo, treinou com o começo de quinta e sexta, que estão no teste do P2
    for role, metadata in client.get("/model").raise_for_status().json().items():
        if metadata.get("protocol") != protocol:
            raise ValueError(
                f"o {ROLES[role]} servido ({metadata['name']}) foi treinado no protocolo "
                f"{metadata.get('protocol')}; o teste de {protocol} pode ter fluxos do treino dele"
            )
    flows = flows.sort_values(schema.TIMESTAMP, kind="stable")
    with closing(_connect(db)) as conn:
        conn.execute("DROP TABLE IF EXISTS verdicts")
        conn.execute(TABLE)
        previous = None
        for timestamp, minute in flows.groupby(schema.TIMESTAMP, sort=True):
            if previous is not None:
                sleep(min(timestamp - previous, MAX_GAP).total_seconds() / speed)
            previous = timestamp
            for start in range(0, len(minute), batch_size):
                batch = minute.iloc[start : start + batch_size]
                body = {"flows": batch[schema.FEATURES].to_dict("records")}
                response = client.post("/predict", json=body)
                response.raise_for_status()
                results = pd.DataFrame(response.json()["results"])
                results = results.rename(columns={"family": "predicted_family"})
                # Só os nomes, do que mais pesou para o que menos: o peso de cada modelo tem a
                # escala dele, e o painel mostra o porquê, não a conta
                results["explanation"] = [
                    ", ".join(c["feature"] for c in why) for why in results["explanation"]
                ]
                rows = batch[KEPT].reset_index(drop=True).join(results)
                rows.to_sql("verdicts", conn, if_exists="append", index=False)
                conn.commit()
            log.info("%s: %d fluxos", timestamp.strftime("%d/%m %H:%M"), len(minute))
    return len(flows)


def read_verdicts(db: Path) -> pd.DataFrame:
    """Todos os vereditos gravados, na ordem em que o replay os mandou."""
    with closing(_connect(db)) as conn:
        query = "SELECT * FROM verdicts ORDER BY rowid"
        return pd.read_sql(query, conn, parse_dates=[schema.TIMESTAMP])


def _connect(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    # WAL: o painel lê enquanto o replay escreve
    conn.execute("PRAGMA journal_mode=WAL")
    return conn
