---
status: aceita
data: 2026-10-28
---

# Avaliar com três protocolos de divisão: aleatório, temporal e por dia

No CIC-IDS2017 cada ataque acontece em um único dia, então nenhuma divisão sozinha responde a todas
as perguntas. Usamos três (`src/nids/data/split.py`):

- **P0, aleatório** estratificado por rótulo (60/20/20): existe só como contraexemplo, para medir
  quanto o split usual infla os resultados.
- **P1, temporal**: dentro de cada dia e rótulo, os primeiros 60 % no tempo vão para o treino, os
  20 % seguintes para a validação e o resto para o teste. Mede a detecção de ataques conhecidos no
  futuro.
- **P2, ataques inéditos**: treino e validação de segunda a quarta (validação = últimos 20 % de cada
  dia e rótulo), teste com quinta e sexta inteiras. Mede a detecção de ataques nunca vistos.

Em todos, as duplicatas saem antes da divisão, e pré-processamento e limiares são ajustados só com
treino e validação.

## Opções consideradas

- **Só o split aleatório:** é o mais comum, mas deixa fluxos vizinhos quase idênticos de uma mesma
  sessão de ataque no treino e no teste.
- **Só a divisão por dia:** o teste teria apenas classes ausentes do treino, o que impede avaliar o
  classificador por classe.
