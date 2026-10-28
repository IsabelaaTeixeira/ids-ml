"""Linha de comando do projeto. Use `uv run nids --help` para ver os comandos."""

import typer

from nids import __version__

app = typer.Typer(
    help="IDS com Machine Learning: dados, treino, avaliação e serviço.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """IDS com Machine Learning."""


@app.command()
def version() -> None:
    """Mostra a versão do pacote."""
    typer.echo(__version__)
