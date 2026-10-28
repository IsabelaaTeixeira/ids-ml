---
status: aceita
data: 2026-10-28
---

# Remover dez atributos que repetem outros

O CICFlowMeter grava várias cópias da mesma medida. A análise exploratória
(`notebooks/01_eda.ipynb`, seção 3) encontrou seis pares de colunas idênticas, três iguais em pelo
menos 99,99 % das linhas e a variância, que é o quadrado do desvio-padrão em quase todas as linhas.
A limpeza remove uma coluna de cada par (lista em `schema.DROPPED`), e os modelos passam de 70 para
60 atributos. Para árvores, as cópias não mudam o desempenho, mas dividem a importância entre
colunas iguais, o que confunde a explicação com SHAP, e alongam a entrada da API.

## Consequências

Entre `fwd_psh_flags` e `syn_flag_count`, idênticas, ficou `fwd_psh_flags` por ser a primeira no
arquivo. A escolha é arbitrária: os valores, maiores que zero em só 7,2 % dos fluxos TCP, não
permitem saber qual dos dois nomes descreve o que o CICFlowMeter mediu.
