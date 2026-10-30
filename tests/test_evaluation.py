import pytest

from nids.evaluation import evaluate


def test_macro_f1_e_a_media_simples_das_classes():
    # A: precisão 2/2, revocação 2/3, F1 0,8. B: precisão 1/2, revocação 1/1, F1 2/3.
    # Macro = (0,8 + 2/3) / 2 = 0,7333; a média ponderada pelo suporte daria 0,7667.
    result = evaluate(["A", "A", "A", "B"], ["A", "A", "B", "B"])

    assert result["macro_f1"] == pytest.approx(0.7333, abs=1e-4)
    assert result["per_class"]["A"] == pytest.approx(
        {"precision": 1.0, "recall": 2 / 3, "f1": 0.8, "support": 3}
    )


def test_classe_prevista_que_nao_existe_conta_com_f1_zero():
    # A: precisão 1/1, revocação 1/2, F1 2/3. C foi prevista, mas nunca aparece: F1 0.
    result = evaluate(["A", "A"], ["A", "C"])

    assert set(result["per_class"]) == {"A", "C"}
    assert result["macro_f1"] == pytest.approx(1 / 3)
