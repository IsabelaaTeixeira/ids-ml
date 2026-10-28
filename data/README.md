# Dados

Esta pasta fica fora do git; só este arquivo é versionado. Os dados brutos são baixados à mão, e os comandos `nids data ...` geram o resto.

| Pasta | Conteúdo | Origem |
|---|---|---|
| `raw/` | CSVs originais do CIC-IDS2017, nunca editados | Download manual |
| `interim/` | `flows.parquet` limpo | `nids data clean` |
| `processed/` | Splits por protocolo (`random/`, `temporal/`, `unseen/`) | `nids data split` |

## Como baixar o CIC-IDS2017

1. Acesse https://www.unb.ca/cic/datasets/ids-2017.html e preencha o formulário de download.
2. Baixe o pacote de CSVs **com Timestamp e IPs** (*GeneratedLabelledFlows*, também chamado de *TrafficLabelling*). O pacote *MachineLearningCSV* não serve, porque não tem Timestamp.
3. Extraia os oito CSVs (de segunda a sexta) para `data/raw/`.

Na etapa 1, os nomes e os checksums SHA-256 dos arquivos esperados vão para `configs/data.yaml`, e `nids data verify` passa a conferir se está tudo certo.
