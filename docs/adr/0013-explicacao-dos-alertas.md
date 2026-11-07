---
status: aceita
data: 2026-11-06
---

# Cada alerta explicado pelo modelo que o disparou

Um alerta sem motivo obriga a analista a abrir o fluxo e adivinhar. Cada `attack` e cada
`suspicious` da API passa a trazer os três atributos que mais pesaram nele, calculados pelo modelo
que o disparou:

- **XGBoost:** a contribuição de cada atributo para a margem (log-odds) da família prevista, com
  `pred_contribs`, o SHAP exato das árvores que o próprio XGBoost calcula.
- **Autoencoder:** o erro quadrático de reconstrução de cada atributo, depois do `symlog` e da
  padronização. O score de anomalia é a média desses erros, então a explicação é a decomposição
  exata do score.

Os `benign` vêm com a lista vazia, assim como os alertas do Random Forest e do Isolation Forest,
que não têm uma decomposição barata e exata. Com `POST /predict?explain=false`, nenhum alerta é
explicado.

## Opções consideradas

- **A biblioteca `shap`:** dá os mesmos valores do TreeSHAP, mas traz numba e llvmlite para a
  imagem da API, para refazer uma conta que o XGBoost já faz.
- **A aproximação do XGBoost (`approx_contribs`, o método de Saabas):** 12 vezes mais rápida, mas,
  em 1.000 ataques do teste do P1, aponta o mesmo atributo principal em só 82 % dos casos e os
  mesmos três em 54 %.
- **Explicar o score de ataque (1 − P(BENIGN)) em vez da família prevista:** esse score não é a
  margem de nenhuma classe, e as contribuições só somam exatamente na margem de cada classe. A
  margem da família prevista responde à pergunta da analista: por que esta família.
- **Explicar todos os fluxos:** os normais são a maioria, ninguém lê a explicação deles, e o custo
  vai para cada fluxo.

## Consequências

- **Custo.** Num lote de 1.000 ataques, o XGBoost do P1 (7 classes, 300 árvores de profundidade 8)
  leva 2,4 s com a explicação, contra 0,1 s sem ela. É justo quando há muitos ataques que a API mais
  precisa responder rápido, e por isso o cliente pode dispensar a explicação. Pontuar o teste do P2
  inteiro com o par do painel leva 138 s com a explicação e 19 s sem.
- **Escala.** O peso tem a escala do modelo que disparou o alerta: log-odds no XGBoost, erro
  padronizado no autoencoder. Os pesos se comparam dentro de um alerta, não entre um `attack` e um
  `suspicious`.
- **Família.** Com o limiar abaixo de 0,5, um `attack` pode ter BENIGN como classe mais provável. A
  explicação usa a família de ataque mais provável, a mesma do campo `family`.
- **Demonstração.** O replay grava só os nomes dos atributos, e o painel os mostra na tabela dos
  últimos alertas.
- **O que a explicação mostra** ([notebook 06](../../notebooks/06_explicacao.ipynb)): no teste do
  P2, os ataques web são reconhecidos pela janela TCP, o atalho do notebook 02, e o DDoS pelo
  comportamento do fluxo. E 22.502 dos alarmes "falsos" do autoencoder têm a mesma explicação dos
  PortScan, porque são a varredura da máquina invadida, rotulada como normal.
