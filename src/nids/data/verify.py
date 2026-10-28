"""Confere os CSVs brutos contra os checksums SHA-256 registrados no repositório.

O arquivo de checksums usa o formato do `sha256sum`, então também dá para
conferir sem o projeto: `sha256sum -c configs/raw_files.sha256` dentro de data/raw.
"""

import hashlib
from pathlib import Path


def sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def record_checksums(raw_dir: Path, checksum_file: Path) -> dict[str, str]:
    """Calcula o SHA-256 de cada CSV em raw_dir e grava em checksum_file."""
    sums = {path.name: sha256(path) for path in sorted(raw_dir.glob("*.csv"))}
    if not sums:
        raise FileNotFoundError(f"Nenhum CSV em {raw_dir}")
    checksum_file.parent.mkdir(parents=True, exist_ok=True)
    lines = "".join(f"{digest}  {name}\n" for name, digest in sums.items())
    checksum_file.write_text(lines, encoding="utf-8", newline="\n")
    return sums


def read_checksums(checksum_file: Path) -> dict[str, str]:
    sums = {}
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            sums[name] = digest
    return sums


def verify_raw(raw_dir: Path, checksum_file: Path) -> list[str]:
    """Devolve os problemas encontrados. Lista vazia quer dizer que está tudo certo."""
    expected = read_checksums(checksum_file)
    problems = []
    for name, digest in expected.items():
        path = raw_dir / name
        if not path.exists():
            problems.append(f"faltando: {name}")
        elif sha256(path) != digest:
            problems.append(f"checksum diferente: {name}")
    problems += [
        f"arquivo inesperado: {path.name}"
        for path in sorted(raw_dir.glob("*.csv"))
        if path.name not in expected
    ]
    return problems
