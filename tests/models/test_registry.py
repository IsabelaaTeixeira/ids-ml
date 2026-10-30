import json

import pandas as pd
import pytest
from sklearn.tree import DecisionTreeClassifier

from nids.models.registry import Model, load_model, save_model


def _saved_model(directory):
    X = pd.DataFrame({"a": [0.0, 1.0, 2.0, 3.0], "b": [1.0, 1.0, 0.0, 0.0]})
    estimator = DecisionTreeClassifier(random_state=0).fit(X, [0, 0, 1, 1])
    save_model(Model(estimator, {"features": ["a", "b"], "classes": ["BENIGN", "DoS"]}), directory)
    return X


def test_modelo_carregado_usa_os_atributos_do_treino_e_devolve_familias(tmp_path):
    X = _saved_model(tmp_path)
    flows = X.assign(destination_port=80.0)[["destination_port", "b", "a"]]  # extra e fora de ordem

    predicted = load_model(tmp_path).predict(flows)

    assert predicted.tolist() == ["BENIGN", "BENIGN", "DoS", "DoS"]


def test_metadados_guardam_atributos_classes_e_versoes(tmp_path):
    _saved_model(tmp_path)

    metadata = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))

    assert metadata["features"] == ["a", "b"]
    assert metadata["classes"] == ["BENIGN", "DoS"]
    assert set(metadata["library_versions"]) == {"scikit-learn", "xgboost"}


def test_avisa_quando_a_versao_da_biblioteca_mudou(tmp_path):
    _saved_model(tmp_path)
    path = tmp_path / "metadata.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata["library_versions"]["scikit-learn"] = "0.0.1"
    path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.warns(UserWarning, match="scikit-learn"):
        load_model(tmp_path)
