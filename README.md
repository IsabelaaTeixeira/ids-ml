# IDS com Machine Learning

Detecção de intrusão em fluxos de rede com o dataset CIC-IDS2017. O projeto compara um classificador supervisionado, bom em ataques conhecidos, com detectores de anomalia, que tentam pegar ataques nunca vistos, e empacota o resultado como uma API em Docker.

> Em construção. Etapa atual: 3, detecção de anomalias. O plano completo está em [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

## Como rodar

Pré-requisitos: [Git](https://git-scm.com/) e [uv](https://docs.astral.sh/uv/).

```bash
uv sync                      # cria o ambiente e instala as dependências
uv run pre-commit install    # ativa as checagens antes de cada commit
uv run pytest                # roda os testes
uv run nids --help           # lista os comandos do projeto
```

Para baixar e processar o dataset, veja [data/README.md](data/README.md). Para abrir os notebooks de
análise em `notebooks/`, instale também o grupo de dependências deles: `uv sync --group notebooks`.

Com os dados processados, cada experimento de `configs/experiments/` treina um classificador ou
detector de anomalia, fixa o limiar de alarme em 1 % de falsos positivos na validação, avalia no
teste e grava o modelo em `models/` e as métricas em `reports/supervised.json` ou
`reports/anomaly.json`:

```bash
uv run nids train configs/experiments/xgb_temporal.yaml
uv run nids train configs/experiments/iforest_unseen.yaml
```

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `src/nids/` | Código do projeto: dados, modelos, avaliação e API |
| `tests/` | Testes automatizados |
| `data/` | Dados brutos e processados, fora do git (veja [data/README.md](data/README.md)) |
| `configs/` | Configuração dos dados e dos experimentos |
| `notebooks/` | Análises (exploratória e resultados) |
| `reports/` | Relatórios de qualidade, divisões, métricas e figuras |
| `docs/` | Arquitetura e registro de decisões (`docs/adr/`) |
