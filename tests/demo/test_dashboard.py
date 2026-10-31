"""O painel do Streamlit, rodado sem navegador, antes e durante o replay."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).parents[2] / "dashboard" / "app.py"


def _run(db: Path, monkeypatch) -> AppTest:
    monkeypatch.setenv("NIDS_DEMO_DB", str(db))
    return AppTest.from_file(str(APP), default_timeout=30).run()


def test_antes_do_replay_o_painel_espera_em_vez_de_quebrar(tmp_path, monkeypatch):
    app = _run(tmp_path / "ainda_nao_existe.db", monkeypatch)

    assert not app.exception
    assert "replay" in app.info[0].value


def test_numeros_do_topo_vem_do_banco(verdicts_db, monkeypatch):
    app = _run(verdicts_db, monkeypatch)

    assert not app.exception
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Fluxos analisados"] == "6"
    assert metrics["Ataques detectados"] == "66,7 %"  # 2 dos 3 ataques
    assert metrics["Alarmes falsos"] == "1"
    assert metrics["Alertas"] == "3"
