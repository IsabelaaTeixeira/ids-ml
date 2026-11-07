"""Detectores de anomalia (etapa 3): aprendem só o tráfego normal e acusam o que foge dele."""

from datetime import UTC, datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from nids.config import ExperimentConfig
from nids.models.registry import Model
from nids.schema import BENIGN


def symlog(X: np.ndarray) -> np.ndarray:
    """log1p que preserva o sinal: comprime as caudas longas e aceita o −1 das janelas TCP."""
    return np.sign(X) * np.log1p(np.abs(X))


class Autoencoder(MLPRegressor):
    """Rede treinada para reconstruir a entrada (ADR 0007). O erro de reconstrução mede a
    anomalia; a camada do meio, mais estreita, é o que impede a rede de só copiar."""

    def fit(self, X, y=None):
        return super().fit(X, X)

    def score_samples(self, X) -> np.ndarray:
        """Erro quadrático médio com o sinal trocado, como no IsolationForest."""
        return -self.feature_errors(X).mean(axis=1)

    def feature_errors(self, X) -> np.ndarray:
        """Erro quadrático de reconstrução de cada atributo: o que mais foge do normal."""
        return np.asarray((self.predict(X) - X) ** 2)


def train_detector(experiment: ExperimentConfig, X: pd.DataFrame, y: pd.Series) -> Model:
    """Ajusta o pré-processamento e o detector só nas linhas normais de X."""
    if experiment.model == "isolation_forest":
        detector = IsolationForest(n_jobs=-1, random_state=experiment.seed, **experiment.params)
    else:
        detector = Autoencoder(random_state=experiment.seed, **experiment.params)
    estimator = make_pipeline(FunctionTransformer(symlog), StandardScaler(), detector)
    estimator.fit(X[y == BENIGN])
    return Model(
        estimator,
        experiment.model_dump()
        | {
            "kind": "anomaly",
            "features": list(X.columns),
            "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        },
    )
