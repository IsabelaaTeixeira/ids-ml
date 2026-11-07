"""Explicação dos alertas: os atributos que mais pesaram em cada veredito."""

import pytest
from fastapi.testclient import TestClient

from nids.serving.api import Settings, create_app
from nids.serving.predictor import load_predictor

from .conftest import flows


@pytest.fixture(scope="module")
def predictor(explained_models_dir):
    return load_predictor(explained_models_dir, "xgboost", "autoencoder")


def test_cada_alerta_traz_os_atributos_que_mais_pesaram(predictor):
    flows_ = flows(
        {"flow_duration": 10.0},  # DoS pelo XGBoost
        {"idle_mean": 10.0},  # PortScan pelo XGBoost
        {"fwd_packets_s": 1e6},  # só o detector estranha
        {},  # normal
    )

    dos, portscan, suspicious, benign = predictor.predict(flows_)

    # O classificador explica a família que deu: cada uma tem o seu atributo
    assert (dos["verdict"], dos["family"]) == ("attack", "DoS")
    assert dos["explanation"][0]["feature"] == "flow_duration"
    assert (portscan["verdict"], portscan["family"]) == ("attack", "PortScan")
    assert portscan["explanation"][0]["feature"] == "idle_mean"
    assert suspicious["verdict"] == "suspicious"
    assert suspicious["explanation"][0]["feature"] == "fwd_packets_s"
    assert benign["explanation"] == []
    assert len(dos["explanation"]) == 3


def test_a_api_devolve_a_explicacao(explained_models_dir):
    settings = Settings(
        model_dir=explained_models_dir, classifier="xgboost", detector="autoencoder"
    )
    client = TestClient(create_app(settings))

    body = {"flows": flows({"flow_duration": 10.0}).to_dict("records")}
    response = client.post("/predict", json=body)

    (result,) = response.json()["results"]
    assert result["verdict"] == "attack"
    assert result["explanation"][0]["feature"] == "flow_duration"
    assert result["explanation"][0]["weight"] > 0


def test_o_cliente_pode_dispensar_a_explicacao(explained_models_dir):
    # A explicação custa caro justo quando há muitos alertas; quem só quer o veredito dispensa
    settings = Settings(
        model_dir=explained_models_dir, classifier="xgboost", detector="autoencoder"
    )
    client = TestClient(create_app(settings))

    body = {"flows": flows({"flow_duration": 10.0}).to_dict("records")}
    response = client.post("/predict", params={"explain": False}, json=body)

    (result,) = response.json()["results"]
    assert result["verdict"] == "attack"
    assert result["explanation"] == []
