import pandas as pd

from nids import schema
from nids.data.split import random_split, split_summary, temporal_split, unseen_split

FRACTIONS = (0.6, 0.2, 0.2)
GROUPS = {
    ("monday", "BENIGN"): 50,
    ("tuesday", "BENIGN"): 50,
    ("tuesday", "FTP-Patator"): 30,
    ("wednesday", "DoS Hulk"): 40,
    ("thursday", "Bot"): 20,
}


def test_random_estratifica_pelo_rotulo(make_flows):
    df = make_flows(GROUPS)

    part = random_split(df, FRACTIONS, seed=1)

    assert part.notna().all()
    counts = pd.crosstab(df[schema.LABEL], part)
    assert counts.loc["FTP-Patator"].to_dict() == {"test": 6, "train": 18, "val": 6}


def test_random_e_reprodutivel(make_flows):
    df = make_flows(GROUPS)

    assert random_split(df, FRACTIONS, seed=1).equals(random_split(df, FRACTIONS, seed=1))
    assert not random_split(df, FRACTIONS, seed=1).equals(random_split(df, FRACTIONS, seed=2))


def test_temporal_respeita_a_ordem_no_tempo(make_flows):
    df = make_flows(GROUPS)

    part = temporal_split(df, FRACTIONS)

    for _, group in df.assign(part=part).groupby([schema.DAY, schema.LABEL], observed=True):
        first = group.groupby("part")[schema.TIMESTAMP].min()
        last = group.groupby("part")[schema.TIMESTAMP].max()
        assert last["train"] <= first["val"]
        assert last["val"] <= first["test"]


def test_unseen_testa_so_nos_dias_nao_vistos(make_flows):
    df = make_flows(GROUPS)

    part = unseen_split(
        df, train_days=["monday", "tuesday"], test_days=["thursday"], val_fraction=0.2
    )

    assert set(df.loc[part == "test", schema.DAY]) == {"thursday"}
    assert set(df.loc[part.isin(["train", "val"]), schema.DAY]) == {"monday", "tuesday"}
    assert part[df[schema.DAY] == "wednesday"].isna().all()
    assert (part == "val").sum() == 26  # 20% de cada (dia, rótulo) de segunda e terça


def test_resumo_conta_por_familia(make_flows):
    df = make_flows({("monday", "BENIGN"): 10, ("tuesday", "SSH-Patator"): 10})

    summary = split_summary(df, temporal_split(df, FRACTIONS))

    assert summary["train"] == {"BENIGN": 6, "BruteForce": 6}
    assert summary["test"] == {"BENIGN": 2, "BruteForce": 2}
