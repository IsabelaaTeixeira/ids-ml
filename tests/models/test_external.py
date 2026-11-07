"""Pontuação de um conjunto externo, pedaço a pedaço, com modelos já treinados."""

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

from nids import schema
from nids.config import ExperimentConfig
from nids.models.anomaly import train_detector
from nids.models.external import score_flows
from nids.models.registry import Model


def _flows(n: int) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    df = pd.DataFrame(rng.normal(0, 1, (n, len(schema.FEATURES))), columns=schema.FEATURES)
    families = rng.choice(["BENIGN", "DoS"], n)
    return df.assign(date="2018-02-14", label=families, family=families, protocol=6.0)


def _models(flows: pd.DataFrame) -> dict[str, Model]:
    y = (flows[schema.FAMILY] == "DoS").astype(int)
    tree = DecisionTreeClassifier(max_depth=3, random_state=0).fit(flows[schema.FEATURES], y)
    metadata = {"kind": "classifier", "features": schema.FEATURES, "classes": ["BENIGN", "DoS"]}
    experiment = ExperimentConfig(
        name="detector", protocol="unseen", model="isolation_forest", params={"n_estimators": 20}
    )
    detector = train_detector(experiment, flows[schema.FEATURES], flows[schema.FAMILY])
    return {"classificador": Model(tree, metadata), "detector": detector}


def test_pontuar_em_pedacos_da_o_mesmo_que_pontuar_tudo_de_uma_vez():
    flows = _flows(10)
    models = _models(flows)
    pieces = [flows.iloc[i : i + 3] for i in range(0, len(flows), 3)]

    whole = score_flows([flows], models)
    chunked = score_flows(pieces, models)

    assert len(chunked) == len(flows)
    assert list(chunked.columns) == ["date", "label", "family", "protocol", *models]
    assert chunked["family"].tolist() == flows["family"].tolist()
    pd.testing.assert_frame_equal(chunked, whole)
    np.testing.assert_allclose(chunked["detector"], models["detector"].score(flows), rtol=1e-6)
