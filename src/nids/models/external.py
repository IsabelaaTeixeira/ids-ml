"""Pontuação de um conjunto externo com modelos já treinados (ADR 0011).

Com dezenas de milhões de fluxos, os dados não cabem na memória de uma vez, mas os scores cabem:
score_flows guarda, por fluxo, só a data, o rótulo, a família, o protocolo e o score de cada
modelo. Limiares, revocação e taxas de falsos positivos saem depois, desse resultado.
"""

from collections.abc import Iterable

import pandas as pd

from nids import schema
from nids.models.registry import Model

KEPT = ["date", schema.LABEL, schema.FAMILY, "protocol"]


def score_flows(chunks: Iterable[pd.DataFrame], models: dict[str, Model]) -> pd.DataFrame:
    """Uma linha por fluxo, com o score de cada modelo (maior = mais suspeito)."""
    parts = []
    for chunk in chunks:
        part = chunk[KEPT].reset_index(drop=True)
        for name, model in models.items():
            part[name] = model.score(chunk).astype("float32")
        parts.append(part)
    scores = pd.concat(parts, ignore_index=True)
    categories = dict.fromkeys(["date", schema.LABEL, schema.FAMILY], "category")
    return scores.astype(categories | {"protocol": "int8"})
