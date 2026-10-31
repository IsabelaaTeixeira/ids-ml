# IDS com Machine Learning

Detecção de intrusão em fluxos de rede com o dataset CIC-IDS2017. O projeto compara um classificador supervisionado, bom em ataques conhecidos, com detectores de anomalia, que tentam pegar ataques nunca vistos, e empacota o resultado como uma API em Docker.

> Em construção. Etapa atual: 5, demonstração com replay e painel. O plano completo está em [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

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

## Demonstração

![Painel durante o replay da tarde de sexta-feira](docs/demo.gif)

O replay manda à API o teste do P2 (quinta e sexta-feira, quase 1 milhão de fluxos) em ordem
cronológica, um minuto de captura por segundo. Cada veredito vai para um banco ao lado do rótulo
verdadeiro, e um painel mostra ao vivo os alertas, os acertos e os erros:

```bash
docker compose --profile demo up --build    # painel em http://localhost:8501
```

O replay inteiro leva cerca de 20 minutos. Para ver só a tarde de sexta, com o PortScan e o DDoS:

```bash
docker compose --profile demo run --rm replay nids replay --api=http://api-demo:8000 \
  --file=/data/processed/unseen/test.parquet --db=/demo/replay.db --start="2017-07-07 13:00"
```

No Git Bash do Windows, comece o comando com `MSYS_NO_PATHCONV=1`: sem isso, ele troca
`/data/...` e `/demo/...` por caminhos do Windows antes de chegarem ao container.

Nessa demonstração, a API serve o XGBoost **do P2**, que nunca viu esses ataques. O do P1, da API
padrão, treinou com o começo de quinta e sexta, e o replay se recusa a usar modelos que podem ter
visto o teste ([ADR 0009](docs/adr/0009-replay-com-modelos-do-p2.md)). Ao fim, o painel mostra
45,4 % dos ataques detectados, o mesmo resultado da combinação de classificador e detector na
avaliação offline, e 70.953 alarmes falsos. Cerca de 80 % desses alarmes são tráfego de ataque que
o conjunto rotula como normal: as respostas da vítima e uma varredura feita pela máquina invadida.

Sem Docker, rode em três terminais:
`NIDS_CLASSIFIER=xgb_unseen uv run uvicorn nids.serving.api:create_app --factory`,
`uv run nids replay` e `uv run streamlit run dashboard/app.py`.

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `src/nids/` | Código do projeto: dados, modelos, avaliação, API e replay |
| `dashboard/` | Painel da demonstração (Streamlit) |
| `docker/` | Imagens da API e da demonstração |
| `tests/` | Testes automatizados |
| `data/` | Dados brutos e processados, fora do git (veja [data/README.md](data/README.md)) |
| `configs/` | Configuração dos dados e dos experimentos |
| `notebooks/` | Análises (exploratória e resultados) |
| `reports/` | Relatórios de qualidade, divisões, métricas e figuras |
| `docs/` | Arquitetura e registro de decisões (`docs/adr/`) |
