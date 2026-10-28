---
status: aceita
data: 2026-10-28
---

# Agrupar os rótulos em famílias e tirar Heartbleed e Infiltration do multiclasse

Os 15 rótulos viram 9 famílias (`schema.LABELS`; por exemplo, os quatro DoS viram DoS). Heartbleed
(11 fluxos) e Infiltration (36) continuam no conjunto, mas ficam fora do treino e da avaliação
multiclasse do P0 e do P1, em que o teste teria 2 e 7 fluxos: com esses números, um acerto a mais
muda a revocação em até 50 pontos. As duas entram só nas avaliações binárias (ataque ou normal),
sempre com o número de amostras ao lado.

## Opções consideradas

- **Manter as duas no multiclasse:** métricas por classe sem significado estatístico.
- **Gerar amostras sintéticas (SMOTE, por exemplo):** inventaria fluxos a partir de 7 a 22 exemplos
  reais de treino.
- **Juntar as duas numa classe "outros":** misturaria ataques sem relação entre si.

## Consequências

A exclusão acontece no treino (etapa 2); o pipeline de dados não muda.
