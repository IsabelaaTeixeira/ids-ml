"""Métricas de classificação. A média é sempre a macro: a ponderada pelo suporte esconde as
famílias raras atrás do tráfego normal."""

from collections.abc import Sequence
from typing import Any

from sklearn.metrics import classification_report


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
