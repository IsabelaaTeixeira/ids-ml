"""Detectores de anomalia: treinam só com tráfego normal e dão score maior ao mais suspeito."""

import numpy as np
import pandas as pd
import pytest

from nids import schema
from nids.config import ExperimentConfig
from nids.models.anomaly import train_detector
from nids.models.registry import load_model, save_model

PARAMS = {
    "isolation_forest": {"n_estimators": 50},
    "autoencoder": {"hidden_layer_sizes": [16, 4, 16], "max_iter": 100},
}


@pytest.mark.parametrize("model", ["isolation_forest", "autoencoder"])
def test_detector_aprende_so_o_normal_e_sobrevive_ao_artefato(tmp_path, model):
    rng = np.random.default_rng(0)
    n = 300
    # Tantos ataques quanto normais: se entrassem no treino, pareceriam normais
    X = pd.DataFrame(
        np.vstack([rng.normal(0, 1, (n, 60)), rng.normal(50, 1, (n, 60))]),
        columns=schema.FEATURES,
    )
    y = pd.Series(["BENIGN"] * n + ["DoS"] * n)
    experiment = ExperimentConfig(
        name="teste", protocol="unseen", model=model, params=PARAMS[model]
    )

    detector = train_detector(experiment, X, y)
    scores = detector.score(X)

    assert scores[y == "DoS"].min() > scores[y == "BENIGN"].max()
    save_model(detector, tmp_path)
    np.testing.assert_allclose(load_model(tmp_path).score(X), scores)
