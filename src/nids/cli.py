"""Linha de comando do projeto. Use `uv run nids --help` para ver os comandos."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from nids import __version__, schema
from nids.config import load_data_config, load_experiment_config
from nids.data.pipeline import run_clean, run_split
from nids.data.verify import record_checksums, verify_raw
from nids.models.experiment import run_experiment

app = typer.Typer(
    help="IDS com Machine Learning: dados, treino, avaliação e serviço.",
    no_args_is_help=True,
)
data_app = typer.Typer(
    help="Pipeline de dados: conferir, limpar e dividir o CIC-IDS2017.",
    no_args_is_help=True,
)
app.add_typer(data_app, name="data")

DataConfigOption = Annotated[
    Path, typer.Option("--config", help="Arquivo de configuração dos dados.")
]
DEFAULT_DATA_CONFIG = Path("configs/data.yaml")


@app.callback()
def main() -> None:
    """IDS com Machine Learning."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")


@app.command()
def version() -> None:
    """Mostra a versão do pacote."""
    typer.echo(__version__)


@app.command()
def train(
    experiment: Annotated[Path, typer.Argument(help="YAML do experimento (configs/experiments/).")],
    config: DataConfigOption = DEFAULT_DATA_CONFIG,
) -> None:
    """Treina um classificador ou detector de anomalia e avalia na validação e no teste."""
    cfg = load_data_config(config)
    exp = load_experiment_config(experiment)
    metrics = run_experiment(exp, cfg.paths)
    if "test" in metrics:
        typer.echo(
            f"{exp.name}: macro-F1 {metrics['val']['macro_f1']:.4f} na validação, "
            f"{metrics['test']['macro_f1']:.4f} no teste"
        )
    detection = metrics["detection"]["test"]
    typer.echo(
        f"{exp.name}: detecção no teste com o limiar da validação: revocação "
        f"{detection['recall']:.4f}, FPR {detection['fpr']:.4f} "
        f"({detection['false_alarms']} alarmes falsos)"
    )
    typer.echo(f"Modelo em {cfg.paths.models / exp.name}")


@app.command()
def score(
    source: Annotated[Path, typer.Argument(help="Zip do CSE-CIC-IDS2018 corrigido.")],
    model: Annotated[
        list[str], typer.Option(help="Modelo de --model-dir; repita a opção para vários.")
    ],
    model_dir: Annotated[Path, typer.Option(help="Pasta dos modelos.")] = Path("models/improved"),
    out: Annotated[Path, typer.Option(help="Parquet com os scores.")] = Path(
        "data/cse2018/scores.parquet"
    ),
    chunksize: Annotated[int, typer.Option(help="Linhas lidas por vez.")] = 1_000_000,
) -> None:
    """Pontua um conjunto externo com modelos treinados, sem carregá-lo inteiro (ADR 0011)."""
    from nids.data.cse2018 import read_chunks
    from nids.models.external import score_flows
    from nids.models.registry import load_model

    models = {name: load_model(model_dir / name) for name in model}
    scores = score_flows(read_chunks(source, chunksize), models)
    out.parent.mkdir(parents=True, exist_ok=True)
    scores.to_parquet(out, index=False)
    typer.echo(f"{len(scores)} fluxos pontuados por {len(models)} modelos; scores em {out}")


@app.command()
def replay(
    api: Annotated[str, typer.Option(help="Endereço da API.")] = "http://localhost:8000",
    file: Annotated[Path, typer.Option(help="Parte de teste a reproduzir.")] = Path(
        "data/processed/unseen/test.parquet"
    ),
    db: Annotated[Path, typer.Option(help="Banco SQLite que o painel lê.")] = Path(
        "data/demo/replay.db"
    ),
    speed: Annotated[
        float, typer.Option(help="Aceleração da captura (60: um minuto por segundo).")
    ] = 60,
    start: Annotated[
        datetime | None,
        typer.Option(
            help="Começa neste horário da captura, ex.: '2017-07-07 13:00'.",
            formats=["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"],
        ),
    ] = None,
) -> None:
    """Manda o teste à API em ordem cronológica e grava os vereditos para o painel."""
    # Só a demonstração precisa do cliente HTTP (grupo de dependências demo)
    import httpx2

    from nids.demo.replay import replay as run_replay

    logging.getLogger("httpx2").setLevel(logging.WARNING)  # uma linha por requisição é demais
    flows = pd.read_parquet(file)
    if start is not None:
        flows = flows[flows[schema.TIMESTAMP] >= start]
    with httpx2.Client(base_url=api, timeout=60) as client:
        try:
            # O protocolo é a pasta da parte: data/processed/<protocolo>/test.parquet
            sent = run_replay(flows, client, db, protocol=file.parent.name, speed=speed)
        except ValueError as error:
            typer.echo(f"Replay recusado: {error}", err=True)
            raise typer.Exit(1) from error
    typer.echo(f"{sent} fluxos enviados; vereditos em {db}")


@data_app.command("verify")
def data_verify(
    config: DataConfigOption = DEFAULT_DATA_CONFIG,
    record: Annotated[
        bool,
        typer.Option("--record", help="Grava os checksums dos CSVs atuais em vez de conferir."),
    ] = False,
) -> None:
    """Confere se os CSVs brutos existem e batem com os checksums registrados."""
    cfg = load_data_config(config)
    if record:
        sums = record_checksums(cfg.paths.raw, cfg.paths.checksums)
        typer.echo(f"{len(sums)} checksums gravados em {cfg.paths.checksums}")
        return
    if not cfg.paths.checksums.exists():
        typer.echo(
            f"{cfg.paths.checksums} não existe. Rode `nids data verify --record` "
            "depois de baixar os CSVs.",
            err=True,
        )
        raise typer.Exit(1)
    problems = verify_raw(cfg.paths.raw, cfg.paths.checksums)
    for problem in problems:
        typer.echo(problem, err=True)
    if problems:
        raise typer.Exit(1)
    typer.echo("Arquivos brutos conferidos: tudo certo.")


@data_app.command("clean")
def data_clean(config: DataConfigOption = DEFAULT_DATA_CONFIG) -> None:
    """Limpa os CSVs brutos e grava o dataset limpo e o relatório de qualidade."""
    cfg = load_data_config(config)
    report = run_clean(cfg)
    typer.echo(f"{report['rows_raw']} linhas brutas -> {report['rows_clean']} linhas limpas")
    for step in report["steps"]:
        if step["removed"]:
            typer.echo(f"  {step['step']}: -{step['removed']}")
    typer.echo(f"Relatório em {cfg.paths.reports / 'data_quality.json'}")


@data_app.command("split")
def data_split(config: DataConfigOption = DEFAULT_DATA_CONFIG) -> None:
    """Divide o dataset limpo nos protocolos random, temporal e unseen."""
    cfg = load_data_config(config)
    summary = run_split(cfg)
    for protocol, parts in summary.items():
        sizes = ", ".join(f"{name} {sum(counts.values())}" for name, counts in parts.items())
        typer.echo(f"{protocol}: {sizes}")
    typer.echo(f"Resumo em {cfg.paths.reports / 'splits.json'}")
