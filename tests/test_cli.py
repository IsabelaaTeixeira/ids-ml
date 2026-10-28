from typer.testing import CliRunner

from nids import __version__
from nids.cli import app

runner = CliRunner()


def test_version_mostra_versao_do_pacote():
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_sem_argumentos_mostra_ajuda():
    result = runner.invoke(app, [])

    assert "Usage" in result.output
