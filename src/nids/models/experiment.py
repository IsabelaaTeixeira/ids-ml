"""Um experimento de ponta a ponta: treina, fixa o limiar na validação, avalia e grava."""

import json
from collections.abc import Sequence
from functools import partial
from pathlib import Path
from typing import Any

import pandas as pd

from nids import schema
from nids.config import ExperimentConfig, Paths
from nids.data.pipeline import write_json
from nids.evaluation import evaluate, evaluate_detection, threshold_at_fpr
from nids.models.anomaly import train_detector
from nids.models.registry import save_model
from nids.models.supervised import EXCLUDED_FAMILIES, train_classifier

ANOMALY_MODELS = ("isolation_forest", "autoencoder")


def load_xy(
    split_dir: Path,
    part: str,
    use_destination_port: bool = False,
    exclude: Sequence[str] = (),
    drop_rare: bool = True,
) -> tuple[pd.DataFrame, pd.Series]:
    """Atributos e família de uma parte do split, sem `exclude`.

    A porta de destino fica de fora por padrão (ADR 0004). As famílias raras também, a não ser
    com drop_rare=False: ficam fora do multiclasse, mas entram na detecção (ADR 0003).
    """
    features = [
        c
        for c in schema.FEATURES
        if (use_destination_port or c != "destination_port") and c not in exclude
    ]
    df = pd.read_parquet(split_dir / f"{part}.parquet", columns=[*features, schema.FAMILY])
    if drop_rare:
        df = df[~df[schema.FAMILY].isin(EXCLUDED_FAMILIES)]
    return df[features], df[schema.FAMILY].astype(str)


def run_experiment(experiment: ExperimentConfig, paths: Paths) -> dict[str, Any]:
    """Treina, avalia na validação e no teste, e grava o modelo e as métricas.

    Todo modelo é avaliado também como detector (ataque contra normal), com o limiar que dá a
    FPR alvo nos fluxos normais da validação, fixado antes de olhar o teste.
    """
    load = partial(
        load_xy,
        paths.processed / experiment.protocol,
        use_destination_port=experiment.use_destination_port,
        exclude=experiment.exclude_features,
    )
    X, y = load("train")
    metrics: dict[str, Any] = {}
    if experiment.model in ANOMALY_MODELS:
        model = train_detector(experiment, X, y)
    else:
        model = train_classifier(experiment, X, y)
        for part in ("val", "test"):
            X_part, y_part = load(part)
            metrics[part] = evaluate(y_part, model.predict(X_part))

    X_val, y_val = load("val", drop_rare=False)
    val_scores = model.score(X_val)
    threshold = threshold_at_fpr(
        val_scores[(y_val == schema.BENIGN).to_numpy()], experiment.target_fpr
    )
    model.metadata["threshold"] = threshold
    X_test, y_test = load("test", drop_rare=False)
    metrics["detection"] = {
        "val": evaluate_detection(y_val, val_scores, threshold),
        "test": evaluate_detection(y_test, model.score(X_test), threshold),
    }

    directory = paths.models / experiment.name
    save_model(model, directory)
    write_json(directory / "metrics.json", metrics)
    report_name = "anomaly" if model.metadata["kind"] == "anomaly" else "supervised"
    report = paths.reports / f"{report_name}.json"
    results = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
    results[experiment.name] = experiment.model_dump(exclude={"name"}) | metrics
    write_json(report, results)
    return metrics
