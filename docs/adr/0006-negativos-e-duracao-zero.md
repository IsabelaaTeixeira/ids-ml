---
status: aceita
data: 2026-10-28
---

# Corrigir tempos negativos e manter os fluxos de duração zero

Três problemas dos dados originais, três regras na limpeza (`src/nids/data/clean.py`):

1. **Tempos negativos viram 0.** São valores de −14 a −1 µs, quase todos em `flow_iat_min`
   (2.891 linhas), que parecem imprecisão do relógio da captura. Remover essas linhas custaria 4 dos
   11 fluxos de Heartbleed e 1 dos 36 de Infiltration.
2. **Fluxos de duração zero ficam, com as taxas por segundo iguais a 0.** São 2.982: 2.867 que já
   tinham duração zero e 115 que passam a ter pela regra 1. Antes, `flow_bytes_s` e
   `flow_packets_s` vinham infinitas ou vazias e o fluxo inteiro era descartado. Taxa 0 é a
   convenção que o próprio CICFlowMeter já usa em `fwd_packets_s` e `bwd_packets_s`, e
   `flow_duration = 0` sinaliza o caso para o modelo. Assim a API também não rejeita fluxos
   instantâneos, que existem em tráfego real.
3. **Fluxos com tamanho de cabeçalho negativo saem.** São 35, todos de tráfego normal, com valores de
   até −32 bilhões: *overflow* de inteiro, sem valor recuperável.

## Consequências

`validate_clean` passa a exigir que nenhum atributo seja negativo, exceto o −1 das janelas TCP
iniciais, que significa "janela não observada" e é informação (equivale a "não é TCP").
