"""Métricas de classificação e de detecção. A média é sempre a macro: a ponderada pelo suporte
esconde as famílias raras atrás do tráfego normal."""

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, classification_report

from nids.schema import BENIGN


def evaluate(y_true: Sequence[str], y_pred: Sequence[str]) -> dict[str, Any]:
    """Macro-F1 e, para cada classe, precisão, revocação, F1 e suporte."""
    labels = sorted(set(y_true) | set(y_pred))
    report = classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
    per_class = {
        label: {
            "precision": report[label]["precision"],
            "recall": report[label]["recall"],
            "f1": report[label]["f1-score"],
            "support": int(report[label]["support"]),
        }
        for label in labels
    }
    return {"macro_f1": report["macro avg"]["f1-score"], "per_class": per_class}


def threshold_at_fpr(benign_scores: Sequence[float], fpr: float) -> float:
    """Menor limiar em que a fração de fluxos normais com score acima dele não passa de `fpr`.

    Um fluxo é alarme quando o score é estritamente maior que o limiar. Com empate no limite,
    o empate inteiro fica abaixo, então a FPR na amostra nunca passa do alvo.
    """
    ordered = np.sort(np.asarray(benign_scores))[::-1]
    return float(ordered[int(fpr * len(ordered))])


def evaluate_detection(
    families: Sequence[str], scores: Sequence[float], threshold: float
) -> dict[str, Any]:
    """Ataque contra normal: alarmes falsos, revocação geral e por família, e PR-AUC.

    O PR-AUC (precisão média) usa só a ordem dos scores e não depende do limiar.
    """
    df = pd.DataFrame({"family": np.asarray(families), "alarm": np.asarray(scores) > threshold})
    attack = df["family"] != BENIGN
    benign_alarms = df.loc[~attack, "alarm"]
    per_family = {
        str(family): {
            "recall": float(alarms.mean()),
            "detected": int(alarms.sum()),
            "support": len(alarms),
        }
        for family, alarms in df.loc[attack].groupby("family", sort=False)["alarm"]
    }
    return {
        "threshold": float(threshold),
        "false_alarms": int(benign_alarms.sum()),
        "fpr": float(benign_alarms.mean()),
        "recall": float(df.loc[attack, "alarm"].mean()),
        "pr_auc": float(average_precision_score(attack, scores)),
        "per_family": per_family,
    }
