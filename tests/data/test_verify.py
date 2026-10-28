from nids.data.verify import record_checksums, verify_raw


def test_registra_e_confere_checksums(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "Monday.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    checksums = tmp_path / "raw_files.sha256"

    record_checksums(raw, checksums)

    assert verify_raw(raw, checksums) == []


def test_acusa_arquivo_alterado_faltando_e_inesperado(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "A.csv").write_text("1\n", encoding="utf-8")
    (raw / "B.csv").write_text("2\n", encoding="utf-8")
    checksums = tmp_path / "raw_files.sha256"
    record_checksums(raw, checksums)

    (raw / "A.csv").write_text("alterado\n", encoding="utf-8")
    (raw / "B.csv").unlink()
    (raw / "C.csv").write_text("3\n", encoding="utf-8")

    assert verify_raw(raw, checksums) == [
        "checksum diferente: A.csv",
        "faltando: B.csv",
        "arquivo inesperado: C.csv",
    ]
