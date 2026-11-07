"""Veredito combinado de um IDS híbrido, sem nada de HTTP: o dashboard pode usar o mesmo código."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from nids.models.registry import Model, load_model
from nids.schema import BENIGN, FEATURES


@dataclass
class Predictor:
    classifier: Model
    detector: Model

    def __post_init__(self) -> None:
        """Confere na subida o que, de outro jeito, só quebraria no primeiro fluxo."""
        for model, kind in ((self.classifier, "classifier"), (self.detector, "anomaly")):
            name, actual = model.metadata["name"], model.metadata["kind"]
            if actual != kind:
                raise ValueError(f"{name}: esperava um modelo {kind}, mas é {actual}")
            # A API só recebe os atributos de schema.FEATURES
            unknown = sorted(set(model.metadata["features"]) - set(FEATURES))
            if unknown:
                raise ValueError(f"{name} usa atributos fora de schema.FEATURES: {unknown}")

    def predict(self, flows: pd.DataFrame, explain: bool = True) -> list[dict]:
        """Um veredito por fluxo: "attack" se o classificador passa do limiar dele, com a
        família; senão "suspicious" se o detector passa do dele; senão "benign". Com `explain`,
        cada alerta traz os atributos que mais pesaram nele."""
        # Os limiares foram calculados sobre Model.score, então o veredito usa o mesmo score
        attack_probability = self.classifier.score(flows)
        anomaly_score = self.detector.score(flows)
        attack = attack_probability > self.classifier.metadata["threshold"]
        anomaly = anomaly_score > self.detector.metadata["threshold"]
        # Com limiar abaixo de 0,5, um fluxo pode ser ataque com BENIGN como classe mais provável
        family = self.classifier.probabilities(flows).drop(columns=BENIGN).idxmax(axis=1)
        verdict = np.where(attack, "attack", np.where(anomaly, "suspicious", "benign"))
        # Cada alerta é explicado pelo modelo que o disparou; os normais ficam sem explicação
        explanation = [[] for _ in range(len(flows))]
        for model, alerted in ((self.classifier, attack), (self.detector, ~attack & anomaly)):
            rows = np.flatnonzero(alerted)
            if explain and rows.size:
                for i, why in zip(rows, model.explain(flows.iloc[rows]), strict=True):
                    explanation[i] = why
        return [
            {
                "verdict": str(v),
                "family": str(f) if v == "attack" else None,
                "attack_probability": float(p),
                "anomaly_score": float(s),
                "explanation": why,
            }
            for v, f, p, s, why in zip(
                verdict, family, attack_probability, anomaly_score, explanation, strict=True
            )
        ]


def load_predictor(model_dir: Path, classifier: str, detector: str) -> Predictor:
    return Predictor(load_model(model_dir / classifier), load_model(model_dir / detector))
