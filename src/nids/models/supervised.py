"""Classificadores supervisionados (etapa 2)."""

from datetime import UTC, datetime
from typing import Any

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from nids.config import ExperimentConfig
from nids.models.registry import Model

# ADR 0003: com 2 a 7 fluxos no teste, as métricas por classe dessas famílias seriam ruído
EXCLUDED_FAMILIES = ("Heartbleed", "Infiltration")


def train_classifier(experiment: ExperimentConfig, X: pd.DataFrame, y: pd.Series) -> Model:
    """Classificador multiclasse das famílias de y."""
    classes = sorted(y.unique())
    estimator = _build(experiment)
    # Pesos inversos à frequência: sem eles, o tráfego normal (83 %) domina o treino
    estimator.fit(X, y.map(classes.index), sample_weight=compute_sample_weight("balanced", y))
    return Model(
        estimator,
        experiment.model_dump()
        | {
            "kind": "classifier",
            "features": list(X.columns),
            "classes": classes,
            "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        },
    )


def _build(experiment: ExperimentConfig) -> Any:
    seed = experiment.seed
    if experiment.model == "xgboost":
        return XGBClassifier(tree_method="hist", n_jobs=-1, random_state=seed, **experiment.params)
    return RandomForestClassifier(n_jobs=-1, random_state=seed, **experiment.params)
