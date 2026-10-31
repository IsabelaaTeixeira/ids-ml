"""O que o painel mostra, calculado a partir do banco do replay."""

import sqlite3
from contextlib import closing

import pytest

from nids.demo.summary import by_family, per_minute, recent_alerts, totals


def test_totais_contam_alertas_acertos_e_alarmes_falsos(verdicts_db):
    result = totals(verdicts_db)

    assert result["flows"] == 6
    assert result["alerts"] == 3
    assert result["attacks"] == 3
    assert result["detected"] == 2
    assert result["false_alarms"] == 1
    assert result["recall"] == pytest.approx(2 / 3)
    assert result["fpr"] == pytest.approx(1 / 3)


def test_no_comeco_do_replay_sem_ataques_a_revocacao_fica_indefinida(verdicts_db):
    with closing(sqlite3.connect(verdicts_db)) as conn, conn:
        conn.execute("DELETE FROM verdicts WHERE family != 'BENIGN'")

    result = totals(verdicts_db)

    assert result["attacks"] == 0
    assert result["recall"] is None
    assert result["fpr"] == pytest.approx(1 / 3)


def test_por_familia_mostra_os_vereditos_de_cada_familia_verdadeira(verdicts_db):
    table = by_family(verdicts_db)

    assert table.index.tolist() == ["BENIGN", "Infiltration", "PortScan"]  # ordem de schema
    assert table["attack"].tolist() == [0, 0, 1]
    assert table["suspicious"].tolist() == [1, 1, 0]
    assert table["benign"].tolist() == [2, 0, 1]
    # Alertas sobre o total: revocação nos ataques, taxa de alarmes falsos nos normais
    assert table["alert_rate"].tolist() == pytest.approx([1 / 3, 1, 1 / 2])


def test_por_minuto_compara_alertas_com_os_ataques_reais(verdicts_db):
    series = per_minute(verdicts_db)

    assert series.index.strftime("%H:%M").tolist() == ["09:00", "09:01"]
    assert series["attack"].tolist() == [1, 0]
    assert series["suspicious"].tolist() == [1, 1]
    assert series["true_attacks"].tolist() == [1, 2]


def test_ultimos_alertas_do_mais_novo_ao_mais_antigo_com_acerto_ou_erro(verdicts_db):
    alerts = recent_alerts(verdicts_db, n=3)

    assert alerts["source_ip"].tolist() == ["10.0.0.5", "10.0.0.3", "10.0.0.2"]
    assert alerts["family"].tolist() == ["Infiltration", "PortScan", "BENIGN"]
    assert alerts["correct"].tolist() == [True, True, False]
