---
status: aceita
data: 2026-10-31
---

# A demonstração reproduz o teste do P2 com os modelos do P2

O replay manda à API o teste do P2 (quinta e sexta-feira inteiras, em ordem cronológica), e a API da
demonstração serve o XGBoost do P2 (`xgb_unseen`) com o autoencoder. A API padrão serve o XGBoost do
P1, que treinou com os primeiros 60 % de cada dia, inclusive quinta e sexta: no teste do P2, cerca de
60 % dos fluxos seriam dados de treino dele, e o painel mostraria acertos inflados. Com os modelos do
P2, nenhum dos dois viu os ataques do replay, e o painel mostra ao vivo a pergunta central do
projeto. Antes de começar, o replay lê `/model` e se recusa a rodar se algum modelo servido foi
treinado em outro protocolo.

## Opções consideradas

- **Reproduzir o teste do P1 com a API padrão:** também não tem dados de treino, mas o teste do P1 é
  só o fim de cada janela de ataque, e a linha do tempo da demonstração ficaria picotada.

## Consequências

- No `docker-compose.yml`, a demonstração tem a própria API (`api-demo`, interna), com
  `NIDS_CLASSIFIER=xgb_unseen`; a API da porta 8000 continua com o XGBoost do P1.
- O classificador do P2 só conhece força bruta e DoS (o Heartbleed fica fora do multiclasse,
  [ADR 0003](0003-familias-e-classes-raras.md)): os ataques que ele pega aparecem com essas famílias.
  No replay, quase todos os ataques web e todo o DDoS detectados saem como DoS.
- A trava compara o protocolo dos modelos com a pasta do teste (`data/processed/<protocolo>/`). Ela é
  conservadora: recusa também combinações que seriam válidas, como o autoencoder no teste do P1.
