"""Treina pela CLI, com um split sintético numa pasta temporária."""

import json

import pytest
import yaml
from typer.testing import CliRunner

from nids.cli import app
from nids.models.registry import load_model
from nids.models.supervised import load_xy

runner = CliRunner()
GROUPS = {
    ("tuesday", "BENIGN"): 30,
    ("tuesday", "FTP-Patator"): 20,
    ("wednesday", "DoS Hulk"): 20,
    ("wednesday", "Heartbleed"): 3,
}


@pytest.mark.parametrize("model", ["xgboost", "random_forest"])
def test_treino_grava_modelo_metadados_e_metricas(tmp_path, make_flows, model):
    split_dir = tmp_path / "processed" / "temporal"
    split_dir.mkdir(parents=True)
    for seed, part in enumerate(("train", "val", "test")):
        make_flows(GROUPS, seed=seed).to_parquet(split_dir / f"{part}.parquet", index=False)
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
    experiment = tmp_path / "experimento.yaml"
    experiment.write_text(
        yaml.safe_dump(
            {
                "name": "teste",
                "protocol": "temporal",
                "model": model,
                "params": {"n_estimators": 5, "max_depth": 3},
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["train", str(experiment), "--config", str(data_config)])

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
