"""Leitura do CSE-CIC-IDS2018 corrigido (Engelen et al.), em pedaços, direto do zip."""

import zipfile

import numpy as np
import pandas as pd
import pytest

from nids import schema
from nids.data.cse2018 import read_chunks
from nids.data.load import RawFormatError

from .test_improved import write_improved_csv


def _zip(tmp_path, name, *overrides):
    csv = write_improved_csv(tmp_path / name, *overrides)
    path = tmp_path / "CSECICIDS2018_improved.zip"
    with zipfile.ZipFile(path, "a") as zf:
        zf.write(csv, arcname=name)
    return path


def test_le_o_2018_com_as_familias_do_2017_e_a_mesma_limpeza_por_fluxo(tmp_path):
    path = _zip(
        tmp_path,
        "Friday-02-03-2018.csv",
        {"Label": "Botnet Ares"},
        {"Label": "SSH-BruteForce"},
        {"Label": "DDoS-LOIC-UDP", "Protocol": 17},
        {"Label": "Infiltration - NMAP Portscan"},
        {"Label": "Infiltration - Dropbox Download"},
        {"Label": "Web Attack - SQL"},
        {"Label": "FTP-BruteForce - Attempted", "Attempted Category": 1},
        {"Flow IAT Min": -3},  # tempo negativo: vira 0
        {"Flow Bytes/s": np.inf},  # infinito: a linha sai
        {"Fwd Header Length": -100},  # overflow: a linha sai
    )

    flows = pd.concat(read_chunks(path, chunksize=4), ignore_index=True)

    assert flows[schema.FAMILY].tolist() == [
        "Bot", "BruteForce", "DDoS", "PortScan", "Infiltration", "WebAttack", "BENIGN", "BENIGN",
    ]  # fmt: skip
    assert (flows["date"] == "2018-03-02").all()
    assert flows["flow_iat_min"].iloc[7] == 0
    assert set(schema.FEATURES) <= set(flows.columns)


def test_rotulo_desconhecido_e_recusado(tmp_path):
    path = _zip(tmp_path, "Friday-02-03-2018.csv", {"Label": "Ataque Novo"})

    with pytest.raises(RawFormatError, match="Ataque Novo"):
        list(read_chunks(path))
