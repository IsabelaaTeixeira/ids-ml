from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from nids.config import DataConfig, ExperimentConfig, load_data_config

DATA_CONFIG = Path(__file__).parents[1] / "configs" / "data.yaml"


def _data_config_dict() -> dict:
    return yaml.safe_load(DATA_CONFIG.read_text(encoding="utf-8"))


def test_config_de_dados_do_repositorio_e_valida():
    config = load_data_config(DATA_CONFIG)

    assert config.split.fractions == (0.6, 0.2, 0.2)
    assert config.split.unseen.test_days == ["thursday", "friday"]


def test_fracoes_precisam_somar_um():
    data = _data_config_dict()
    data["split"]["fractions"] = [0.5, 0.2, 0.2]

    with pytest.raises(ValidationError, match="somar 1"):
        DataConfig.model_validate(data)


def test_dia_nao_pode_estar_no_treino_e_no_teste():
    data = _data_config_dict()
    data["split"]["unseen"]["test_days"] = ["wednesday", "thursday"]

    with pytest.raises(ValidationError, match="wednesday"):
        DataConfig.model_validate(data)


def test_dia_desconhecido_falha():
    data = _data_config_dict()
    data["split"]["unseen"]["train_days"] = ["saturday"]

    with pytest.raises(ValidationError):
        DataConfig.model_validate(data)


def test_exclusao_de_atributos_confere_os_nomes():
    experiment = {"name": "x", "protocol": "temporal", "model": "xgboost"}

    valid = ExperimentConfig.model_validate(experiment | {"exclude_features": ["protocol"]})
    assert valid.exclude_features == ["protocol"]
    with pytest.raises(ValidationError, match="atributos desconhecidos"):
        ExperimentConfig.model_validate(experiment | {"exclude_features": ["init_win_bytes"]})
