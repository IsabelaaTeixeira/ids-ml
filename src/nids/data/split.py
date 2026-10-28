"""Protocolos de divisão treino/validação/teste (seção 6 da arquitetura).

Cada protocolo devolve uma Series alinhada ao DataFrame com "train", "val", "test"
ou NaN para linhas que ficam fora do protocolo.
"""

from collections.abc import Sequence

import numpy as np
import pandas as pd

from nids import schema
from nids.config import SplitConfig

PARTS = ("train", "val", "test")
PROTOCOLS = ("random", "temporal", "unseen")


def _split_groups(ordered: pd.DataFrame, keys: list[str], fractions: Sequence[float]) -> pd.Series:
    """Corta cada grupo em partes consecutivas, na ordem em que as linhas aparecem."""
    groups = ordered.groupby(keys, observed=True, sort=False)
    position = groups.cumcount().to_numpy()
    size = groups[schema.ROW_ID].transform("size").to_numpy()
    cuts = np.round(np.outer(size, np.cumsum(fractions)[:-1]))
    part = (position[:, None] >= cuts).sum(axis=1)
    return pd.Series(np.asarray(PARTS)[part], index=ordered.index)


def random_split(df: pd.DataFrame, fractions: Sequence[float], seed: int) -> pd.Series:
    """P0: aleatório, estratificado pelo rótulo. Existe só como contraexemplo."""
    shuffled = df.sample(frac=1, random_state=seed)
    return _split_groups(shuffled, [schema.LABEL], fractions).reindex(df.index)


def temporal_split(df: pd.DataFrame, fractions: Sequence[float]) -> pd.Series:
    """P1: dentro de cada (dia, rótulo), as primeiras linhas no tempo vão para o treino."""
    ordered = df.sort_values([schema.TIMESTAMP, schema.ROW_ID])
    return _split_groups(ordered, [schema.DAY, schema.LABEL], fractions).reindex(df.index)


def unseen_split(
    df: pd.DataFrame, train_days: Sequence[str], test_days: Sequence[str], val_fraction: float
) -> pd.Series:
    """P2: treino e validação nos train_days (validação = final de cada dia), teste nos
    test_days inteiros. Dias fora das duas listas ficam de fora."""
    in_train_days = df[schema.DAY].isin(train_days)
    part = temporal_split(df[in_train_days], (1 - val_fraction, val_fraction))
    part = part.reindex(df.index)
    part[df[schema.DAY].isin(test_days)] = "test"
    return part


def make_split(df: pd.DataFrame, protocol: str, config: SplitConfig) -> pd.Series:
    match protocol:
        case "random":
            return random_split(df, config.fractions, config.seed)
        case "temporal":
            return temporal_split(df, config.fractions)
        case "unseen":
            unseen = config.unseen
            return unseen_split(df, unseen.train_days, unseen.test_days, unseen.val_fraction)
    raise ValueError(f"Protocolo desconhecido: {protocol}")


def split_summary(df: pd.DataFrame, part: pd.Series) -> dict[str, dict[str, int]]:
    """Quantas linhas de cada família caíram em cada parte."""
    table = pd.crosstab(df[schema.FAMILY], part)
    return {
        p: {str(family): int(n) for family, n in table[p].items() if n}
        for p in PARTS
        if p in table.columns
    }
