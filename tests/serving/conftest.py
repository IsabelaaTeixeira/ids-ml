"""Modelos minúsculos de verdade, salvos como os da etapa 3, para testar o serviço."""

import numpy as np
import pandas as pd
import pytest
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier

from nids import schema
from nids.config import ExperimentConfig
from nids.evaluation import threshold_at_fpr
from nids.models.anomaly import train_detector
from nids.models.registry import Model, save_model

# O classificador só olha flow_duration. As folhas da árvore dão probabilidades exatas:
#   0 -> 10 normais                          P(ataque) = 0
#   1 -> 6 normais, 3 DoS, 1 PortScan        P(ataque) = 0,4, mas a classe mais provável é BENIGN
#   2 -> 10 PortScan                         P(ataque) = 1
CLASSIFIER_THRESHOLD = 0.3
_TREE_DATA = [(0, "BENIGN")] * 10 + [(1, "BENIGN")] * 6 + [(1, "DoS")] * 3 + [(1, "PortScan")]
_TREE_DATA += [(2, "PortScan")] * 10


def flows(*overrides: dict) -> pd.DataFrame:
    """Um fluxo por dicionário: todos os atributos de schema.FEATURES em 0, menos os dados."""
    return pd.DataFrame([dict.fromkeys(schema.FEATURES, 0.0) | o for o in overrides])


def _classifier() -> Model:
    classes = ["BENIGN", "DoS", "PortScan"]
    X = pd.DataFrame({"flow_duration": [float(d) for d, _ in _TREE_DATA]})
    y = [classes.index(label) for _, label in _TREE_DATA]
    tree = DecisionTreeClassifier(random_state=0).fit(X, y)
    metadata = {
        "name": "classificador",
        "protocol": "unseen",
        "kind": "classifier",
        "features": ["flow_duration"],
        "classes": classes,
        "threshold": CLASSIFIER_THRESHOLD,
        "trained_at": "2026-10-31T00:00:00+00:00",
    }
    return Model(tree, metadata)


def _detector() -> Model:
    """Isolation Forest que aprendeu total_fwd_packets ~ N(0, 1): 1000 pacotes é anomalia."""
    rng = np.random.default_rng(0)
    X = pd.DataFrame({"total_fwd_packets": rng.normal(0, 1, 500)})
    y = pd.Series([schema.BENIGN] * len(X))
    experiment = ExperimentConfig(
        name="detector", protocol="unseen", model="isolation_forest", params={"n_estimators": 50}
    )
    detector = train_detector(experiment, X, y)
    detector.metadata["threshold"] = threshold_at_fpr(detector.score(X), 0.01)
    return detector


# Os modelos que se explicam. Os cinco atributos são ~ N(0, 1) nos normais, que é tudo o que o
# autoencoder viu; no XGBoost, um atributo separa cada família: flow_duration perto de 10 no DoS
# e idle_mean perto de 10 no PortScan
EXPLAINED = ["flow_duration", "total_fwd_packets", "flow_bytes_s", "fwd_packets_s", "idle_mean"]
SEPARATES = {"DoS": "flow_duration", "PortScan": "idle_mean"}


def _xgboost(normal: pd.DataFrame, rng: np.random.Generator) -> Model:
    classes = ["BENIGN", *SEPARATES]
    attacks = []
    for feature in SEPARATES.values():
        attack = pd.DataFrame(rng.normal(0, 1, normal.shape), columns=EXPLAINED)
        attack[feature] = rng.normal(10, 1, len(attack))
        attacks.append(attack)
    X = pd.concat([normal, *attacks], ignore_index=True)
    y = np.repeat(np.arange(len(classes)), len(normal))
    xgb = XGBClassifier(n_estimators=20, max_depth=2, random_state=0).fit(X, y)
    metadata = {
        "name": "xgboost",
        "protocol": "unseen",
        "kind": "classifier",
        "features": EXPLAINED,
        "classes": classes,
        "threshold": 0.5,
    }
    return Model(xgb, metadata)


def _autoencoder(normal: pd.DataFrame) -> Model:
    experiment = ExperimentConfig(
        name="autoencoder",
        protocol="unseen",
        model="autoencoder",
        params={"hidden_layer_sizes": [4], "max_iter": 300},
    )
    detector = train_detector(experiment, normal, pd.Series([schema.BENIGN] * len(normal)))
    detector.metadata["threshold"] = threshold_at_fpr(detector.score(normal), 0.01)
    return detector


@pytest.fixture(scope="session")
def explained_models_dir(tmp_path_factory):
    """Pasta com os modelos "xgboost" e "autoencoder", os dois tipos que explicam o alerta."""
    rng = np.random.default_rng(0)
    normal = pd.DataFrame(rng.normal(0, 1, (300, len(EXPLAINED))), columns=EXPLAINED)
    directory = tmp_path_factory.mktemp("explained")
    save_model(_xgboost(normal, rng), directory / "xgboost")
    save_model(_autoencoder(normal), directory / "autoencoder")
    return directory


@pytest.fixture(scope="session")
def models_dir(tmp_path_factory):
    """Pasta com os modelos "classificador" e "detector", no formato de models/."""
    directory = tmp_path_factory.mktemp("models")
    save_model(_classifier(), directory / "classificador")
    save_model(_detector(), directory / "detector")
    return directory
