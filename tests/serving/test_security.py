"""Proteção e operação da API: chave de acesso, limite de requisições e métricas."""

import pytest
from fastapi.testclient import TestClient

from nids.serving.api import Settings, create_app

from .conftest import flows

KEY = "segredo-de-teste"


def _client(models_dir, **settings):
    base = {"model_dir": models_dir, "classifier": "classificador", "detector": "detector"}
    return TestClient(create_app(Settings(**base, **settings)))


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "chave-errada"}], ids=["sem", "errada"])
def test_sem_a_chave_certa_da_401_e_o_health_continua_aberto(models_dir, headers):
    client = _client(models_dir, api_key=KEY)
    body = {"flows": flows({}).to_dict("records")}

    assert client.post("/predict", json=body, headers=headers).status_code == 401
    assert client.get("/model", headers=headers).status_code == 401
    assert client.get("/health").status_code == 200
    assert client.post("/predict", json=body, headers={"X-API-Key": KEY}).status_code == 200


def test_passando_do_limite_por_minuto_da_429(models_dir):
    client = _client(models_dir, rate_limit=2)
    body = {"flows": flows({}).to_dict("records")}

    codes = [client.post("/predict", json=body).status_code for _ in range(3)]

    assert codes == [200, 200, 429]
    assert client.get("/health").status_code == 200


def test_metrics_conta_os_vereditos_por_tipo_e_mede_a_latencia(models_dir):
    client = _client(models_dir)
    # Um ataque (flow_duration 2 é PortScan no classificador de teste) e dois normais
    body = {"flows": flows({"flow_duration": 2.0}, {}, {}).to_dict("records")}

    client.post("/predict", json=body)
    text = client.get("/metrics").text

    assert 'nids_verdicts_total{verdict="attack"} 1.0' in text
    assert 'nids_verdicts_total{verdict="benign"} 2.0' in text
    assert "nids_predict_seconds_count 1.0" in text
