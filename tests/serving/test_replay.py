"""Replay: o teste passa pela API em ordem cronológica e cada veredito vai para o banco."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from nids.demo.replay import read_verdicts, replay
from nids.serving.api import Settings, create_app

from .conftest import flows


@pytest.fixture(scope="module")
def client(models_dir):
    settings = Settings(model_dir=models_dir, classifier="classificador", detector="detector")
    return TestClient(create_app(settings))


def _capture(*rows: tuple[str, str, str, dict]) -> pd.DataFrame:
    """Fluxos como no teste do P2: (horário, IP de origem, família verdadeira, atributos)."""
    data = flows(*(features for *_, features in rows))
    return data.assign(
        timestamp=pd.to_datetime([t for t, *_ in rows]),
        source_ip=[ip for _, ip, *_ in rows],
        destination_ip="192.168.10.50",
        family=[family for _, _, family, _ in rows],
    )


def test_cada_fluxo_vai_para_o_banco_com_veredito_e_rotulo_na_ordem_do_tempo(client, tmp_path):
    capture = _capture(
        ("2017-07-06 09:01", "10.0.0.4", "PortScan", {"flow_duration": 2.0}),
        ("2017-07-06 09:00", "10.0.0.1", "BENIGN", {}),
        ("2017-07-06 09:00", "10.0.0.2", "Infiltration", {"total_fwd_packets": 1000.0}),
        ("2017-07-06 09:00", "10.0.0.3", "BENIGN", {}),
    )
    db = tmp_path / "replay.db"

    replay(capture, client, db, protocol="unseen", batch_size=2, sleep=lambda seconds: None)

    saved = read_verdicts(db)
    assert saved["source_ip"].tolist() == ["10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4"]
    assert saved["family"].tolist() == ["BENIGN", "Infiltration", "BENIGN", "PortScan"]
    assert saved["verdict"].tolist() == ["benign", "suspicious", "benign", "attack"]
    assert saved["predicted_family"].fillna("").tolist() == ["", "", "", "PortScan"]


def test_ritmo_segue_a_captura_acelerada_e_comprime_a_madrugada(client, tmp_path):
    capture = _capture(
        ("2017-07-06 09:00", "10.0.0.1", "BENIGN", {}),
        ("2017-07-06 09:01", "10.0.0.1", "BENIGN", {}),
        ("2017-07-06 09:03", "10.0.0.1", "BENIGN", {}),
        ("2017-07-07 09:00", "10.0.0.1", "BENIGN", {}),  # o dia seguinte
    )
    waits = []

    replay(capture, client, tmp_path / "replay.db", protocol="unseen", speed=60, sleep=waits.append)

    # 1 minuto de captura por segundo; a noite entre os dias vira o máximo de 5 minutos
    assert waits == pytest.approx([1, 2, 5])


def test_recusa_teste_de_outro_protocolo_que_os_modelos_podem_ter_visto(client, tmp_path):
    # Os modelos servidos são do P2: o teste do P1 tem fluxos do treino deles
    capture = _capture(("2017-07-06 09:00", "10.0.0.1", "BENIGN", {}))
    db = tmp_path / "replay.db"

    with pytest.raises(ValueError, match="classificador"):
        replay(capture, client, db, protocol="temporal", sleep=lambda seconds: None)
    assert not db.exists()
