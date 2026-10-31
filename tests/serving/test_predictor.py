"""Veredito combinado: ataque pelo classificador, suspeito pelo detector, normal pelos dois."""

import pytest

from nids.serving.predictor import load_predictor

from .conftest import flows


@pytest.fixture(scope="module")
def predictor(models_dir):
    return load_predictor(models_dir, classifier="classificador", detector="detector")


def test_classificador_decide_o_ataque_e_detector_o_suspeito(predictor):
    results = predictor.predict(
        flows(
            {},  # nenhum dos dois dispara
            {"total_fwd_packets": 1000.0},  # só o detector
            {"flow_duration": 2.0},  # só o classificador
            {"flow_duration": 2.0, "total_fwd_packets": 1000.0},  # os dois: ataque ganha
        )
    )

    assert [r["verdict"] for r in results] == ["benign", "suspicious", "attack", "attack"]
    assert [r["family"] for r in results] == [None, None, "PortScan", "PortScan"]
    assert [r["attack_probability"] for r in results] == pytest.approx([0, 0, 1, 1])


def test_familia_e_o_ataque_mais_provavel_mesmo_quando_benign_lidera(predictor):
    # P(BENIGN) = 0,6, P(DoS) = 0,3, P(PortScan) = 0,1: passa do limiar de 0,3 como ataque
    [result] = predictor.predict(flows({"flow_duration": 1.0}))

    assert result["verdict"] == "attack"
    assert result["family"] == "DoS"
    assert result["attack_probability"] == pytest.approx(0.4)
