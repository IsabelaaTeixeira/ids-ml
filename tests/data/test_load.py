from pathlib import Path

import numpy as np
import pytest

from nids import schema
from nids.data.load import RawFormatError, day_from_filename, load_raw, read_raw_csv


def test_dia_vem_do_nome_do_arquivo():
    assert day_from_filename(Path("Wednesday-workingHours.pcap_ISCX.csv")) == "wednesday"


def test_nome_de_arquivo_sem_dia_falha():
    with pytest.raises(RawFormatError):
        day_from_filename(Path("fluxos.csv"))


def test_le_csv_no_formato_original(tmp_path, write_raw_csv):
    path = write_raw_csv(
        tmp_path / "Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv",
        {"label": "Web Attack – Brute Force", "flow_bytes_s": "Infinity"},
        dict.fromkeys(schema.RAW_COLUMNS),  # linha só com vírgulas
    )

    df = read_raw_csv(path)

    assert list(df.columns) == [schema.DAY, *schema.RAW_COLUMNS]
    assert df[schema.DAY].tolist() == ["thursday", "thursday"]
    assert df.loc[0, schema.LABEL] == "Web Attack \x96 Brute Force"
    assert df.loc[0, "flow_bytes_s"] == np.inf
    assert df["flow_duration"].dtype == np.float32
    assert df.loc[1].drop(schema.DAY).isna().all()


def test_cabecalho_diferente_falha(tmp_path):
    path = tmp_path / "Monday-WorkingHours.pcap_ISCX.csv"
    path.write_text("Flow ID,Label\nx,BENIGN\n", encoding="utf-8")

    with pytest.raises(RawFormatError, match="Faltando"):
        read_raw_csv(path)


def test_load_raw_ordena_os_dias_e_numera_as_linhas(tmp_path, write_raw_csv):
    write_raw_csv(tmp_path / "Tuesday-WorkingHours.pcap_ISCX.csv", {}, {})
    write_raw_csv(tmp_path / "Monday-WorkingHours.pcap_ISCX.csv", {})

    df = load_raw(tmp_path)

    assert df[schema.ROW_ID].tolist() == [0, 1, 2]
    assert df[schema.DAY].tolist() == ["monday", "tuesday", "tuesday"]


def test_load_raw_sem_csv_falha(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_raw(tmp_path)
