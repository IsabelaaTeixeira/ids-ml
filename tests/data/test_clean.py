import numpy as np
import pandas as pd
import pytest

from nids import schema
from nids.data.clean import (
    clean,
    clip_negative_times,
    drop_columns,
    drop_duplicates,
    drop_empty_rows,
    drop_header_overflow,
    drop_missing_values,
    fill_instant_rates,
    normalize_labels,
    parse_timestamps,
)
from nids.data.validate import DataValidationError, validate_clean


def test_remove_linhas_sem_rotulo(raw_frame):
    df, _ = drop_empty_rows(raw_frame({}, {"label": None}))

    assert df[schema.ROW_ID].tolist() == [0]


def test_rotulos_viram_canonicos_e_ganham_familia(raw_frame):
    raw = raw_frame(
        {"label": "Web Attack \x96 Brute Force"}, {"label": "FTP-Patator "}, {"label": "BENIGN"}
    )

    df, details = normalize_labels(raw)

    assert df[schema.LABEL].tolist() == ["Web Attack - Brute Force", "FTP-Patator", "BENIGN"]
    assert df[schema.FAMILY].tolist() == ["WebAttack", "BruteForce", "BENIGN"]
    assert details["renamed"] == {
        "Web Attack \x96 Brute Force": "Web Attack - Brute Force",
        "FTP-Patator ": "FTP-Patator",
    }


def test_rotulo_desconhecido_falha(raw_frame):
    with pytest.raises(ValueError, match="Rótulos desconhecidos"):
        normalize_labels(raw_frame({"label": "Ataque Novo"}))


def test_remove_colunas_descartadas(raw_frame):
    df, details = drop_columns(raw_frame({}, {}))

    assert not set(schema.DROPPED) & set(df.columns)
    assert details["bwd_psh_flags"] == {"reason": "constante", "distinct_values": 1}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("03/07/2017 08:55:58", "2017-07-03 08:55:58"),
        ("3/7/2017 9:05", "2017-07-03 09:05"),
        ("3/7/2017 12:30", "2017-07-03 12:30"),
        ("3/7/2017 1:05", "2017-07-03 13:05"),  # relógio de 12h: 1:05 da tarde
        ("03/07/2017 05:10:00", "2017-07-03 17:10"),
    ],
)
def test_converte_timestamp_e_corrige_relogio_de_12h(raw_frame, text, expected):
    df, _ = parse_timestamps(raw_frame({"timestamp": text}), first_capture_hour=8)

    assert df[schema.TIMESTAMP].iloc[0] == pd.Timestamp(expected)


def test_remove_timestamp_invalido_ou_de_outro_dia(raw_frame):
    raw = raw_frame(
        {"timestamp": "03/07/2017 10:00:00"},
        {"timestamp": "04/07/2017 10:00:00"},  # terça num arquivo de segunda
        {"timestamp": "ontem"},
    )

    df, details = parse_timestamps(raw, first_capture_hour=8)

    assert df[schema.ROW_ID].tolist() == [0]
    assert details["wrong_date"] == 1
    assert details["unparsed"] == 1


def test_tempos_negativos_viram_zero(raw_frame):
    df, details = clip_negative_times(raw_frame({"flow_iat_min": -1.0}, {"flow_duration": -13.0}))

    assert df["flow_iat_min"].iloc[0] == 0
    assert df["flow_duration"].iloc[1] == 0
    assert details["clipped"] == {"flow_duration": 1, "flow_iat_min": 1}


def test_fluxo_de_duracao_zero_fica_com_taxas_zeradas(raw_frame):
    raw = raw_frame(
        {"flow_duration": 0.0, "flow_bytes_s": np.nan, "flow_packets_s": np.inf},
        {"flow_duration": 5.0, "flow_bytes_s": 10.0},
    )

    df, details = fill_instant_rates(raw)

    assert df.loc[0, schema.RATE_FEATURES].tolist() == [0, 0, 0, 0]
    assert df.loc[1, "flow_bytes_s"] == 10
    assert details["instant_flows"] == 1


def test_remove_cabecalho_com_overflow(raw_frame):
    df, _ = drop_header_overflow(raw_frame({}, {"fwd_header_length": -32212234240.0}))

    assert df[schema.ROW_ID].tolist() == [0]


def test_remove_infinitos_e_nulos(raw_frame):
    raw = raw_frame(
        {}, {"flow_bytes_s": np.inf}, {"flow_packets_s": -np.inf}, {"flow_iat_mean": np.nan}
    )

    df, details = drop_missing_values(raw)

    assert df[schema.ROW_ID].tolist() == [0]
    assert details["infinite"] == {"flow_bytes_s": 1, "flow_packets_s": 1}
    assert details["missing"] == {"flow_bytes_s": 1, "flow_packets_s": 1, "flow_iat_mean": 1}


def test_duplicata_exata_mantem_a_primeira_no_tempo(raw_frame):
    raw = raw_frame(
        {"flow_duration": 5.0, "timestamp": pd.Timestamp("2017-07-03 10:00")},
        {"flow_duration": 5.0, "timestamp": pd.Timestamp("2017-07-03 09:00")},
        {"flow_duration": 6.0, "timestamp": pd.Timestamp("2017-07-03 09:30")},
    )

    df, details = drop_duplicates(raw)

    assert df[schema.ROW_ID].tolist() == [1, 2]
    assert details["exact"] == 1


def test_duplicatas_conflitantes_saem_todas(raw_frame):
    when = pd.Timestamp("2017-07-03 09:00")
    raw = raw_frame(
        {"flow_duration": 5.0, "label": "BENIGN", "timestamp": when},
        {"flow_duration": 5.0, "label": "DDoS", "timestamp": when},
        {"flow_duration": 6.0, "timestamp": when},
    )

    df, details = drop_duplicates(raw)

    assert df[schema.ROW_ID].tolist() == [2]
    assert details["conflicting"] == 2


def test_clean_completo_passa_na_validacao(raw_frame):
    raw = raw_frame(
        {},  # duração zero (flow_duration = índice da linha): fica, com taxas 0
        {"label": "DDoS"},
        {"label": None},  # linha vazia
        {"flow_bytes_s": np.inf},  # infinito com duração maior que zero
        {"flow_duration": 0.0},  # duplicata da primeira linha
        {"label": "Web Attack \x96 XSS", "timestamp": "3/7/2017 2:10"},
        {"label": "Heartbleed", "flow_iat_min": -1.0},  # tempo negativo: vira 0 e fica
        {"fwd_header_length": -1e9},  # overflow
    )

    df, report = clean(raw)

    validate_clean(df)
    assert report["rows_raw"] == 8
    assert report["rows_clean"] == 4
    assert report["families"] == {"BENIGN": 1, "DDoS": 1, "WebAttack": 1, "Heartbleed": 1}
    removed = {s["step"]: s["removed"] for s in report["steps"] if s["removed"]}
    assert removed == {
        "drop_empty_rows": 1,
        "drop_header_overflow": 1,
        "drop_missing_values": 1,
        "drop_duplicates": 1,
    }


def test_validacao_acusa_infinito(make_flows):
    df = make_flows({("monday", "BENIGN"): 5})
    df.loc[0, "flow_bytes_s"] = np.inf

    with pytest.raises(DataValidationError, match="flow_bytes_s"):
        validate_clean(df)


def test_validacao_acusa_negativo_fora_das_janelas_tcp(make_flows):
    df = make_flows({("monday", "BENIGN"): 5})
    df.loc[0, "init_win_bytes_forward"] = -1.0  # "janela não observada" é permitido
    validate_clean(df)

    df.loc[0, "flow_iat_min"] = -1.0
    with pytest.raises(DataValidationError, match="negativos"):
        validate_clean(df)


def test_validacao_acusa_duplicata(make_flows):
    df = make_flows({("monday", "BENIGN"): 5})
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)

    with pytest.raises(DataValidationError, match="duplicadas"):
        validate_clean(df)
