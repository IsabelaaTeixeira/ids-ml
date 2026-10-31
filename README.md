# IDS com Machine Learning

Detecção de intrusão em fluxos de rede com o dataset CIC-IDS2017. O projeto compara um classificador supervisionado, bom em ataques conhecidos, com detectores de anomalia, que tentam pegar ataques nunca vistos, e empacota o resultado como uma API em Docker.

> Em construção. Etapa atual: 4, serviço de inferência. O plano completo está em [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

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

## API

Com `xgb_temporal` e `ae_unseen` treinados em `models/`, a API sobe com [Docker](https://docs.docker.com/get-started/get-docker/):

```bash
docker compose up --build    # http://localhost:8000/docs mostra as rotas
```

Sem Docker, use `uv run uvicorn nids.serving.api:create_app --factory`.

`POST /predict` recebe `{"flows": [...]}`, com até 1000 fluxos. Cada fluxo traz os 60 atributos do
dataset limpo (os de `schema.FEATURES`). A resposta tem um veredito por fluxo:

- `attack`, com a família, quando o classificador reconhece um ataque conhecido;
- `suspicious`, quando ele não reconhece, mas o detector de anomalia dispara;
- `benign`, nos demais casos.

Os limiares são os escolhidos na validação ([ADR 0008](docs/adr/0008-contrato-da-api.md)).
`GET /model` mostra os modelos carregados e os limiares, e `GET /health` confirma que a API está no ar.

### Testando com fluxos reais

[docs/exemplo_predict.json](docs/exemplo_predict.json) traz três fluxos do teste do P2: um DDoS,
um da infiltração e um normal. Em http://localhost:8000/docs, abra `POST /predict`, clique em
**Try it out**, cole o conteúdo do arquivo e clique em **Execute**. Pelo terminal:

```bash
curl -X POST http://localhost:8000/predict -H "content-type: application/json" -d @docs/exemplo_predict.json
```

No PowerShell, use `curl.exe` em vez de `curl`. A resposta traz um resultado por fluxo, nesta ordem:

| Fluxo | `verdict` | `family` | `attack_probability` | `anomaly_score` |
|---|---|---|---|---|
| DDoS | `attack` | DDoS | 0,9999998 | 0,044 |
| Infiltration | `suspicious` | | 0,00001 | 0,101 |
| Normal | `benign` | | 0,00002 | 0,067 |

- `attack_probability` é a probabilidade de ataque dada pelo XGBoost. Acima de 0,34, o fluxo é
  `attack`, com a família.
- `anomaly_score` mede o quanto o fluxo foge do tráfego normal, segundo o autoencoder. Acima de
  0,072, o fluxo é `suspicious`.

O XGBoost reconhece o DDoS, que viu no treino. A infiltração ele não conhece, mas o autoencoder a
acha estranha. Os limiares exatos estão em `GET /model`.

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
