"""Fluxos reais do teste pela API, com os modelos de models/. Precisa do dataset: fora do CI.

As contagens esperadas vêm de reports/, gravados pela avaliação das etapas 2 e 3 com os mesmos
modelos e limiares: a API tem de chegar ao mesmo resultado que a avaliação offline.
"""

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from nids import schema
from nids.serving.api import Settings, create_app

pytestmark = pytest.mark.data

PROCESSED = Path("data/processed")
REPORTS = Path("reports")
BATCH = 1000


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(Settings()))  # o padrão do serviço: xgb_temporal e ae_unseen


def _test_flows(protocol: str, family: str) -> pd.DataFrame:
    test = pd.read_parquet(
        PROCESSED / protocol / "test.parquet", columns=[*schema.FEATURES, schema.FAMILY]
    )
    return test[test[schema.FAMILY] == family]


def _results(client, flows: pd.DataFrame) -> list[dict]:
    results = []
    for start in range(0, len(flows), BATCH):
        batch = flows.iloc[start : start + BATCH][schema.FEATURES].to_dict("records")
        response = client.post("/predict", json={"flows": batch})
        assert response.status_code == 200
        results += response.json()["results"]
    return results


def _report(name: str, experiment: str) -> dict:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))[experiment]


def test_api_reproduz_a_avaliacao_do_classificador_no_portscan(client):
    results = _results(client, _test_flows("temporal", "PortScan"))
    report = _report("supervised.json", "xgb_temporal")

    attacks = [r for r in results if r["verdict"] == "attack"]
    assert len(attacks) == report["detection"]["test"]["per_family"]["PortScan"]["detected"]
    # Quem tem PortScan como classe mais provável passa de 0,5 e, portanto, do limiar
    portscan = report["test"]["per_class"]["PortScan"]
    expected_family = round(portscan["recall"] * portscan["support"])
    assert sum(r["family"] == "PortScan" for r in attacks) >= expected_family


def test_api_aponta_a_infiltracao_que_o_detector_pegou_na_etapa_3(client):
    results = _results(client, _test_flows("unseen", "Infiltration"))
    report = _report("anomaly.json", "ae_unseen")

    caught = report["detection"]["test"]["per_family"]["Infiltration"]["detected"]
    assert sum(r["verdict"] != "benign" for r in results) >= caught
