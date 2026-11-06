---
status: aceita
data: 2026-11-06
---

# Repetir os experimentos no CIC-IDS2017 corrigido, pelo mesmo pipeline

O [ADR 0001](0001-versao-do-conjunto.md) manteve os rótulos originais e deixou a versão corrigida
como extensão. Ela é feita aqui com a versão mais recente de Engelen et al. (2022,
<https://intrusion-detection.distrinet-research.be/CNS2022/>), gerada com o extrator de fluxos
consertado e com rótulos refeitos a partir das capturas. Os CSVs entram pelo mesmo pipeline:
`load_improved` (`nids/data/improved.py`) entrega o formato da leitura original, e a limpeza, as
divisões, os treinos e a avaliação são os mesmos, com `configs/data_improved.yaml` mandando tudo
para pastas próprias (`data/improved/`, `reports/improved/`, `models/improved/`).

Na conversão:

- os atributos que mudaram de nome são mapeados para os 60 do conjunto original; os atributos novos
  (flags RST por sentido, ICMP, tempo total do fluxo TCP) ficam de fora, para a comparação usar as
  mesmas entradas;
- os fluxos "Attempted", de ataque sem conteúdo malicioso, viram normais, como os autores
  recomendam;
- "Botnet" vira Bot, e a varredura feita pela máquina invadida ("Infiltration - Portscan") vira
  PortScan. Ela é de quinta e a varredura externa é de sexta, então o dia separa as duas;
- o horário, em UTC no arquivo, vira o horário local da captura (UTC−3), o da agenda dos ataques.

## Opções consideradas

- **A primeira versão corrigida (Engelen et al., 2021):** foi substituída pelos próprios autores em
  2022, com rótulos melhorados.
- **A varredura da infiltração na família Infiltration:** a família passaria de 36 para dezenas de
  milhares de fluxos, quase todos da varredura, e deixaria de ser comparável com a do original.
- **Usar também os atributos novos:** mudaria as entradas dos modelos, e a diferença nos resultados
  deixaria de poder ser atribuída aos rótulos e à construção dos fluxos.

## Consequências

- As diferenças entre os resultados misturam dois efeitos: os rótulos refeitos e os fluxos montados
  pelo extrator consertado. Não dá para separá-los com estes dados.
- As redundâncias do [ADR 0005](0005-atributos-redundantes.md) foram medidas no original. Algumas
  vinham de defeitos do extrator antigo e podem não valer aqui; os mesmos 60 atributos são mantidos
  para a comparação.
