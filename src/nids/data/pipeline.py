"""Etapas do pipeline de dados, lendo e gravando nas pastas definidas no config."""

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from nids.config import DataConfig
from nids.data.clean import clean
from nids.data.load import load_raw
from nids.data.split import PARTS, PROTOCOLS, make_split, split_summary
from nids.data.validate import validate_clean

log = logging.getLogger(__name__)

CLEAN_FILE = "flows.parquet"


def run_clean(config: DataConfig) -> dict[str, Any]:
    """raw/*.csv -> interim/flows.parquet + reports/data_quality.json."""
    raw = load_raw(config.paths.raw)
    log.info("Limpando %d linhas", len(raw))
    df, report = clean(raw, first_capture_hour=config.timestamp.first_capture_hour)
    del raw
    validate_clean(df)

    config.paths.interim.mkdir(parents=True, exist_ok=True)
    df.to_parquet(config.paths.interim / CLEAN_FILE, index=False)
    write_json(config.paths.reports / "data_quality.json", report)
    return report


def run_split(config: DataConfig) -> dict[str, Any]:
    """interim/flows.parquet -> processed/<protocolo>/<parte>.parquet + reports/splits.json."""
    df = pd.read_parquet(config.paths.interim / CLEAN_FILE)
    summary = {}
    for protocol in PROTOCOLS:
        log.info("Dividindo pelo protocolo %s", protocol)
        part = make_split(df, protocol, config.split)
        out_dir = config.paths.processed / protocol
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in PARTS:
            df[part == name].reset_index(drop=True).to_parquet(
                out_dir / f"{name}.parquet", index=False
            )
        summary[protocol] = split_summary(df, part)
    write_json(config.paths.reports / "splits.json", summary)
    return summary


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
