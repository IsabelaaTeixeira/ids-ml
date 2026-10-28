"""Roda o pipeline de dados inteiro pela CLI, com CSVs sintéticos numa pasta temporária."""

import json

import yaml
from typer.testing import CliRunner

from nids.cli import app

runner = CliRunner()


def test_pipeline_de_dados_pela_cli(tmp_path, write_raw_csv):
    raw = tmp_path / "raw"
    raw.mkdir()
    write_raw_csv(
        raw / "Monday-WorkingHours.pcap_ISCX.csv",
        *[{"timestamp": f"03/07/2017 09:{m:02d}:00"} for m in range(20)],
    )
    write_raw_csv(
        raw / "Tuesday-WorkingHours.pcap_ISCX.csv",
        *[
            {
                "timestamp": f"4/7/2017 2:{m:02d}",
                "label": "FTP-Patator" if m % 2 else "BENIGN",
                "flow_duration": float(100 + m),
            }
            for m in range(20)
        ],
    )
    config = tmp_path / "data.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "paths": {
                    "raw": str(raw),
                    "interim": str(tmp_path / "interim"),
                    "processed": str(tmp_path / "processed"),
                    "reports": str(tmp_path / "reports"),
                    "checksums": str(tmp_path / "raw_files.sha256"),
                },
                "timestamp": {"first_capture_hour": 8},
                "split": {
                    "seed": 0,
                    "fractions": [0.6, 0.2, 0.2],
                    "unseen": {
                        "train_days": ["monday"],
                        "test_days": ["tuesday"],
                        "val_fraction": 0.2,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    for command in (["verify", "--record"], ["verify"], ["clean"], ["split"]):
        result = runner.invoke(app, ["data", *command, "--config", str(config)])
        assert result.exit_code == 0, f"{command}: {result.output}\n{result.exception!r}"

    report = json.loads((tmp_path / "reports" / "data_quality.json").read_text(encoding="utf-8"))
    assert report["rows_clean"] == 40
    splits = json.loads((tmp_path / "reports" / "splits.json").read_text(encoding="utf-8"))
    assert splits["unseen"]["test"] == {"BENIGN": 10, "BruteForce": 10}
    for protocol in ("random", "temporal", "unseen"):
        for part in ("train", "val", "test"):
            assert (tmp_path / "processed" / protocol / f"{part}.parquet").exists()
