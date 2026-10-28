---
status: aceita
data: 2026-10-28
---

# Treinar sem a porta de destino por padrão

Só com a porta de destino, um classificador trivial (a família mais comum de cada porta no treino)
chega a macro-F1 de 0,33 no P1 e reconhece 96 % do PortScan e 100 % do Bot
(`notebooks/01_eda.ipynb`, seção 6). Boa parte disso é atalho do laboratório: portas escolhidas pelo
atacante, como a 444 em Heartbleed e Infiltration e a 8080 do servidor de comando do Bot, que não se
repetem em outras redes. A porta fica no conjunto limpo, mas sai das entradas do modelo por padrão,
e um experimento com ela mede quanto contribui.

## Consequências

- Endereços IP, porta de origem e horário já ficam fora do modelo, como metadados.
- Um atalho continua, porque não depende de coluna nenhuma: 100 % dos ataques são TCP e 43 % do
  tráfego normal é UDP, então o modelo vai aprender que "UDP = normal". Não há o que remover; entra
  nas limitações do README.
