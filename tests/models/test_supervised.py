from nids import schema
from nids.models.supervised import load_xy

GROUPS = {
    ("tuesday", "BENIGN"): 5,
    ("tuesday", "FTP-Patator"): 5,
    ("wednesday", "Heartbleed"): 3,
    ("thursday", "Infiltration"): 3,
}


def test_modelo_nao_ve_porta_metadados_nem_classes_raras(tmp_path, make_flows):
    make_flows(GROUPS).to_parquet(tmp_path / "train.parquet", index=False)

    X, y = load_xy(tmp_path, "train")

    assert len(X.columns) == 59  # 60 atributos menos a porta de destino (ADR 0004)
    assert "destination_port" not in X.columns
    assert not set(schema.METADATA) & set(X.columns)
    assert sorted(y.unique()) == ["BENIGN", "BruteForce"]  # sem as classes raras (ADR 0003)
    assert len(X) == len(y) == 10


def test_experimento_com_a_porta_inclui_a_coluna(tmp_path, make_flows):
    make_flows(GROUPS).to_parquet(tmp_path / "train.parquet", index=False)

    X, _ = load_xy(tmp_path, "train", use_destination_port=True)

    assert "destination_port" in X.columns
