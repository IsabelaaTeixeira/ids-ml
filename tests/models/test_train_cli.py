"""Treina pela CLI, com um split sintético numa pasta temporária."""

import json

import pytest
import yaml
from typer.testing import CliRunner

from nids.cli import app
from nids.models.experiment import load_xy
from nids.models.registry import load_model

runner = CliRunner()
GROUPS = {
    ("tuesday", "BENIGN"): 30,
    ("tuesday", "FTP-Patator"): 20,
    ("wednesday", "DoS Hulk"): 20,
    ("wednesday", "Heartbleed"): 3,
}


UNSEEN = {
    "train": {("tuesday", "BENIGN"): 40, ("tuesday", "FTP-Patator"): 10},
    "val": {("tuesday", "BENIGN"): 40, ("wednesday", "Heartbleed"): 2},
    "test": {("thursday", "BENIGN"): 40, ("thursday", "Infiltration"): 3, ("friday", "Bot"): 10},
}


def _write_configs(tmp_path, protocol, parts, make_flows, experiment):
    """Split sintético em processed/<protocol>, config dos dados e YAML do experimento."""
    split_dir = tmp_path / "processed" / protocol
    split_dir.mkdir(parents=True)
    for seed, (part, groups) in enumerate(parts.items()):
        make_flows(groups, seed=seed).to_parquet(split_dir / f"{part}.parquet", index=False)
    paths = {name: str(tmp_path / name) for name in ("raw", "interim", "processed", "reports")}
    data_config = tmp_path / "data.yaml"
    data_config.write_text(
        yaml.safe_dump(
            {
                "paths": paths
                | {"checksums": str(tmp_path / "x.sha256"), "models": str(tmp_path / "models")},
                "timestamp": {"first_capture_hour": 8},
                "split": {
                    "seed": 0,
                    "fractions": [0.6, 0.2, 0.2],
                    "unseen": {
                        "train_days": ["monday"],
                        "test_days": ["friday"],
                        "val_fraction": 0.2,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    experiment_file = tmp_path / "experimento.yaml"
    experiment_file.write_text(
        yaml.safe_dump({"name": "teste", "protocol": protocol} | experiment), encoding="utf-8"
    )
    return split_dir, ["train", str(experiment_file), "--config", str(data_config)]


@pytest.mark.parametrize("model", ["xgboost", "random_forest"])
def test_treino_grava_modelo_metadados_e_metricas(tmp_path, make_flows, model):
    split_dir, args = _write_configs(
        tmp_path,
        "temporal",
        dict.fromkeys(("train", "val", "test"), GROUPS),
        make_flows,
        {"model": model, "params": {"n_estimators": 5, "max_depth": 3}},
    )

    result = runner.invoke(app, args)

    assert result.exit_code == 0, f"{result.output}\n{result.exception!r}"
    saved = load_model(tmp_path / "models" / "teste")
    assert saved.metadata["classes"] == ["BENIGN", "BruteForce", "DoS"]  # sem Heartbleed
    assert saved.metadata["protocol"] == "temporal"
    X_test, _ = load_xy(split_dir, "test")
    assert set(saved.predict(X_test)) <= {"BENIGN", "BruteForce", "DoS"}
    report = json.loads((tmp_path / "reports" / "supervised.json").read_text(encoding="utf-8"))
    assert report["teste"]["model"] == model
    assert 0 <= report["teste"]["test"]["macro_f1"] <= 1
    assert set(report["teste"]["test"]["per_class"]) <= {"BENIGN", "BruteForce", "DoS"}


@pytest.mark.parametrize(
    ("model", "params", "report_name"),
    [
        ("isolation_forest", {"n_estimators": 10}, "anomaly"),
        ("xgboost", {"n_estimators": 5, "max_depth": 3}, "supervised"),
    ],
)
def test_limiar_sai_da_validacao_e_a_deteccao_inclui_as_familias_raras(
    tmp_path, make_flows, model, params, report_name
):
    _, args = _write_configs(
        tmp_path,
        "unseen",
        UNSEEN,
        make_flows,
        {"model": model, "params": params, "target_fpr": 0.1},
    )

    result = runner.invoke(app, args)

    assert result.exit_code == 0, f"{result.output}\n{result.exception!r}"
    saved = load_model(tmp_path / "models" / "teste")
    report = json.loads((tmp_path / "reports" / f"{report_name}.json").read_text(encoding="utf-8"))
    detection = report["teste"]["detection"]
    assert saved.metadata["threshold"] == detection["val"]["threshold"]
    assert detection["test"]["threshold"] == detection["val"]["threshold"]
    assert detection["val"]["fpr"] <= 0.1
    # Infiltration e Heartbleed ficam fora do multiclasse, mas entram na detecção (ADR 0003)
    assert set(detection["val"]["per_family"]) == {"Heartbleed"}
    assert set(detection["test"]["per_family"]) == {"Infiltration", "Bot"}
