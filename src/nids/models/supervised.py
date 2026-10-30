"""Classificadores supervisionados (etapa 2)."""

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from nids import schema
from nids.config import ExperimentConfig, Paths
from nids.data.pipeline import write_json
from nids.evaluation import evaluate
from nids.models.registry import Model, save_model

# ADR 0003: com 2 a 7 fluxos no teste, as métricas por classe dessas famílias seriam ruído
EXCLUDED_FAMILIES = ("Heartbleed", "Infiltration")


def load_xy(
    split_dir: Path,
    part: str,
    use_destination_port: bool = False,
    exclude: Sequence[str] = (),
) -> tuple[pd.DataFrame, pd.Series]:
    """Atributos e família de uma parte do split, sem as classes raras e sem `exclude`.

    A porta de destino fica de fora por padrão (ADR 0004).
    """
    features = [
        c
        for c in schema.FEATURES
        if (use_destination_port or c != "destination_port") and c not in exclude
    ]
    df = pd.read_parquet(split_dir / f"{part}.parquet", columns=[*features, schema.FAMILY])
    df = df[~df[schema.FAMILY].isin(EXCLUDED_FAMILIES)]
    return df[features], df[schema.FAMILY].astype(str)


def run_experiment(experiment: ExperimentConfig, paths: Paths) -> dict[str, Any]:
    """Treina, avalia na validação e no teste, e grava o modelo e as métricas."""
    split_dir = paths.processed / experiment.protocol
    X, y = load_xy(split_dir, "train", experiment.use_destination_port, experiment.exclude_features)
    classes = sorted(y.unique())
    estimator = _build(experiment)
    # Pesos inversos à frequência: sem eles, o tráfego normal (83 %) domina o treino
    estimator.fit(X, y.map(classes.index), sample_weight=compute_sample_weight("balanced", y))
    model = Model(
        estimator,
        experiment.model_dump()
        | {
            "features": list(X.columns),
            "classes": classes,
            "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        },
    )

    metrics = {}
    for part in ("val", "test"):
        X_part, y_part = load_xy(
            split_dir, part, experiment.use_destination_port, experiment.exclude_features
        )
        metrics[part] = evaluate(y_part, model.predict(X_part))

    directory = paths.models / experiment.name
    save_model(model, directory)
    write_json(directory / "metrics.json", metrics)
    report = paths.reports / "supervised.json"
    results = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
    results[experiment.name] = experiment.model_dump(exclude={"name"}) | metrics
    write_json(report, results)
    return metrics


def _build(experiment: ExperimentConfig) -> Any:
    seed = experiment.seed
    if experiment.model == "xgboost":
        return XGBClassifier(tree_method="hist", n_jobs=-1, random_state=seed, **experiment.params)
    return RandomForestClassifier(n_jobs=-1, random_state=seed, **experiment.params)
