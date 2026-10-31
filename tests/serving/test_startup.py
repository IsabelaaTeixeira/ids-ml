"""Subida da API: com um artefato incompatível, a API não sobe em vez de errar depois."""

import pytest

from nids.models.registry import load_model, save_model
from nids.serving.api import Settings, create_app


def test_nao_sobe_se_o_modelo_usa_atributo_fora_do_schema(models_dir, tmp_path):
    classifier = load_model(models_dir / "classificador")
    classifier.metadata["features"] = ["flow_duration", "source_ip"]
    save_model(classifier, tmp_path / "classificador")
    save_model(load_model(models_dir / "detector"), tmp_path / "detector")
    settings = Settings(model_dir=tmp_path, classifier="classificador", detector="detector")

    with pytest.raises(ValueError, match="source_ip"):
        create_app(settings)


def test_nao_sobe_com_os_modelos_trocados(models_dir):
    settings = Settings(model_dir=models_dir, classifier="detector", detector="classificador")

    with pytest.raises(ValueError, match="classifier"):
        create_app(settings)
