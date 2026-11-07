---
status: aceita
data: 2026-11-06
---

# Testar os modelos do 2017 corrigido no CSE-CIC-IDS2018 corrigido

Para saber se os modelos valem fora da rede em que foram treinados, eles são avaliados no
CSE-CIC-IDS2018, do mesmo laboratório, mas com outras máquinas, numa rede na AWS. É usada a versão
corrigida por Engelen e Joosen (2022), gerada com o mesmo extrator consertado do CIC-IDS2017
corrigido ([ADR 0010](0010-conjunto-corrigido.md)): treino e teste têm atributos calculados da mesma
forma, e a diferença está só na rede e nos ataques.

Os modelos são os treinados no 2017 corrigido (XGBoost do P1, com e sem os atributos de TCP,
autoencoder e Isolation Forest), cada um com o limiar escolhido na validação de 2017. A avaliação
cobre os 10 dias do 2018 (63 milhões de fluxos), lidos direto do zip em pedaços, com a mesma limpeza
por fluxo do pipeline. Os rótulos vão para o vocabulário do 2017: "Attempted" vira normal, "Botnet
Ares" vira Bot, os ataques de força bruta viram Patator, HOIC e LOIC viram DDoS, a varredura NMAP
da infiltração vira PortScan e o restante da infiltração vira Infiltration.

Além do limiar de 2017, o limiar de cada modelo é recalibrado para 1 % de falsos positivos usando
só o tráfego normal do primeiro dia de 2018 (14/02), e avaliado nos outros nove dias. É o que faria
quem implanta o IDS numa rede nova: observar o tráfego normal antes de ligar os alarmes, sem
nenhum exemplo de ataque.

## Opções consideradas

- **Os CSVs originais do CSE-CIC-IDS2018 com os modelos do 2017 original:** os dois têm erros de
  rótulo e de construção de fluxos, que se misturariam ao efeito da troca de rede.
- **Remover duplicatas no 2018:** a remoção serve para o mesmo fluxo não cair no treino e no teste,
  e aqui o treino é outro conjunto. Em 63 milhões de linhas, ela exigiria guardar todos os fluxos
  na memória.

## Consequências

- O DDoS LOIC-UDP (2.527 fluxos, os únicos ataques por UDP) testa o atalho do protocolo. Como os
  rótulos viram famílias, ele é separado dos outros DDoS pelo protocolo.
- A força bruta por FTP do 2018 é toda "Attempted", então a família BruteForce só tem SSH; o
  Heartleech não aparece nos rótulos. Ataques web (283 fluxos) e infiltração (289) são pequenos.
- Os scores ficam em `data/cse2018/scores.parquet` (fora do git), e as análises saem desse arquivo.
- A regra do [ADR 0006](0006-negativos-e-duracao-zero.md) que descarta tamanhos de cabeçalho
  negativos tira 1.209 dos 2.527 fluxos de DDoS por UDP: o campo estoura como um inteiro de 16 bits
  (valores de −32.752 a −48) em fluxos longos. A mesma regra tira, no 2017 corrigido, 3 dos 11 fluxos
  de Heartbleed e 5 dos 36 de infiltração. Corrigir o valor em vez de descartar a linha seria
  ambíguo, porque o campo pode ter estourado mais de uma vez.
