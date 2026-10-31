"""Contrato HTTP da API: o que entra, o que sai e o que é recusado."""

import json

import pytest
from fastapi.testclient import TestClient

from nids.serving.api import Settings, create_app

from .conftest import flows

MAX_BATCH = 3


@pytest.fixture(scope="module")
def client(models_dir):
    settings = Settings(
        model_dir=models_dir, classifier="classificador", detector="detector", max_batch=MAX_BATCH
    )
    return TestClient(create_app(settings))


def _post(client, records):
    # json.dumps escreve NaN e Infinity, que o httpx se recusa a mandar
    content = json.dumps({"flows": records})
    return client.post("/predict", content=content, headers={"content-type": "application/json"})


def test_predict_devolve_um_veredito_por_fluxo_na_ordem(client):
    body = {"flows": flows({"flow_duration": 2.0}, {}).to_dict("records")}

    response = client.post("/predict", json=body)

    assert response.status_code == 200
    data = response.json()
    assert data["models"] == {"classifier": "classificador", "detector": "detector"}
    assert [r["verdict"] for r in data["results"]] == ["attack", "benign"]
    assert data["results"][0]["family"] == "PortScan"


def test_health_e_model_descrevem_o_servico(client):
    assert client.get("/health").json() == {"status": "ok"}

    models = client.get("/model").json()

    assert models["classifier"]["threshold"] == pytest.approx(0.3)
    assert models["classifier"]["classes"] == ["BENIGN", "DoS", "PortScan"]
    assert models["detector"]["features"] == ["total_fwd_packets"]
    assert set(models["detector"]["library_versions"]) == {"scikit-learn", "xgboost"}


def _one_flow(**changes):
    record = flows({}).to_dict("records")[0]
    return [{k: v for k, v in (record | changes).items() if v is not None}]


@pytest.mark.parametrize(
    "records",
    [
        pytest.param(_one_flow(flow_duration=None), id="atributo faltando"),
        pytest.param(_one_flow(flow_duration=float("nan")), id="NaN"),
        pytest.param(_one_flow(flow_bytes_s=float("inf")), id="infinito"),
        pytest.param(_one_flow(source_ip="192.168.10.5"), id="campo extra"),
        pytest.param([], id="lote vazio"),
        pytest.param(_one_flow() * (MAX_BATCH + 1), id="lote acima do limite"),
    ],
)
def test_entrada_invalida_e_recusada_com_422(client, records):
    assert _post(client, records).status_code == 422
