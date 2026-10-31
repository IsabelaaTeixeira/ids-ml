"""Artefato do modelo: o estimador salvo com os metadados de que o serviço precisa para usá-lo."""

import json
import warnings
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from nids.data.pipeline import write_json
from nids.schema import BENIGN

# Um joblib pode quebrar entre versões dessas bibliotecas
LIBRARIES = ("scikit-learn", "xgboost")


@dataclass
class Model:
    estimator: Any
    metadata: dict[str, Any]  # precisa de "kind" e "features"; classificadores, de "classes"

    def predict(self, flows: pd.DataFrame) -> np.ndarray:
        """Família prevista para cada fluxo, usando só os atributos do treino, na mesma ordem."""
        codes = self.estimator.predict(flows[self.metadata["features"]])
        return np.asarray(self.metadata["classes"])[codes]

    def probabilities(self, flows: pd.DataFrame) -> pd.DataFrame:
        """Só classificadores: a probabilidade de cada família, uma coluna por classe."""
        proba = self.estimator.predict_proba(flows[self.metadata["features"]])
        return pd.DataFrame(proba, columns=self.metadata["classes"], index=flows.index)

    def score(self, flows: pd.DataFrame) -> np.ndarray:
        """Quanto maior, mais suspeito: P(ataque) no classificador, anomalia no detector."""
        X = flows[self.metadata["features"]]
        if self.metadata["kind"] == "anomaly":
            # score_samples segue o scikit-learn: maior para o que parece normal
            return -self.estimator.score_samples(X)
        benign = self.metadata["classes"].index(BENIGN)
        return 1 - self.estimator.predict_proba(X)[:, benign]


def save_model(model: Model, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    joblib.dump(model.estimator, directory / "model.joblib")
    versions = {lib: version(lib) for lib in LIBRARIES}
    write_json(directory / "metadata.json", model.metadata | {"library_versions": versions})


def load_model(directory: Path) -> Model:
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    for lib, saved in metadata["library_versions"].items():
        if version(lib) != saved:
            warnings.warn(
                f"{lib} {version(lib)} instalado, mas o modelo foi salvo com {saved}", stacklevel=2
            )
    return Model(joblib.load(directory / "model.joblib"), metadata)
