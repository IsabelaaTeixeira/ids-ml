import numpy as np
import pytest

from nids.evaluation import evaluate, evaluate_detection, threshold_at_fpr


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


def test_limiar_deixa_passar_so_a_fpr_alvo_dos_normais():
    # Scores de 1 a 100: com FPR de 5%, só os cinco maiores (96 a 100) passam do limiar
    assert threshold_at_fpr(np.arange(1, 101), 0.05) == 95


def test_limiar_com_empate_no_topo_nao_passa_da_fpr_alvo():
    # Seis fluxos empatados em 100: aceitar o empate daria 6 % de FPR, acima dos 5 %
    scores = [*range(1, 95), *[100] * 6]

    assert threshold_at_fpr(scores, 0.05) == 100


def test_deteccao_conta_alarmes_falsos_e_revocacao_por_familia():
    families = ["BENIGN"] * 4 + ["DoS"] * 2 + ["Bot"] * 2
    scores = [0.1, 0.2, 0.3, 0.9, 0.8, 0.4, 0.95, 0.05]

    result = evaluate_detection(families, scores, threshold=0.5)

    # Um normal acima do limiar (0,9); um fluxo de cada ataque acima, um abaixo
    assert result["false_alarms"] == 1
    assert result["fpr"] == pytest.approx(0.25)
    assert result["recall"] == pytest.approx(0.5)
    assert result["per_family"] == {
        "DoS": {"recall": 0.5, "detected": 1, "support": 2},
        "Bot": {"recall": 0.5, "detected": 1, "support": 2},
    }
    # Precisão média, do maior score ao menor: 1/4·1 + 1/4·2/3 + 1/4·3/4 + 1/4·4/8
    assert result["pr_auc"] == pytest.approx(0.7292, abs=1e-4)
