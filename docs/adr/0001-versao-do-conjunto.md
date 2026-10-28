---
status: aceita
data: 2026-10-28
---

# Usar a versão original do CIC-IDS2017, com os rótulos como publicados

Usamos os CSVs originais do pacote *GeneratedLabelledFlows*, e não a versão corrigida de Engelen et
al. (2021), porque é a versão da maior parte da literatura e torna os resultados comparáveis. Os
rótulos não são alterados. A análise exploratória (`notebooks/01_eda.ipynb`, seção 2) confirmou que
os ataques batem com a agenda publicada pelo CIC, com duas exceções que não dá para resolver só com
os fluxos: Bot, com 24 % dos fluxos fora da janela oficial, e SSH-Patator, deslocado cerca de
10 minutos.

## Opções consideradas

- **Versão corrigida de Engelen et al.:** fluxos e rótulos melhores, mas pouco comparável com outros
  trabalhos. Fica como extensão.
- **Corrigir os rótulos pela agenda oficial:** descartaria fluxos do botnet que podem ser maliciosos
  de verdade fora da janela (comunicação com o servidor de comando), trocando um erro por outro.
- **UNSW-NB15:** plano B caso o CIC-IDS2017 se mostrasse inadequado, o que não aconteceu.

## Consequências

Parte dos erros dos modelos pode vir de rótulos errados. As divergências entram nas limitações do
README.
