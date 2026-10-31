---
status: aceita
data: 2026-10-31
---

# A API recebe fluxos já limpos e devolve o veredito combinado com os limiares do treino

`POST /predict` recebe uma lista de fluxos no formato do dataset limpo: os 60 atributos de
`schema.FEATURES`, finitos, sem campos a mais. Cada modelo usa só os atributos que estão nos seus
metadados. O veredito é `attack` se 1 − P(BENIGN) passa do limiar do classificador, `suspicious` se
não passa mas o escore de anomalia passa do limiar do detector, e `benign` nos outros casos. Os dois
limiares são os da etapa 3, lidos dos metadados, e os escores são os mesmos do `Model.score` usado
para escolhê-los. A família de um `attack` é a classe de ataque mais provável: com limiar abaixo de
0,5, um fluxo pode passar do limiar com BENIGN como classe mais provável, e nesse caso a família
não pode ser o argmax.

## Opções consideradas

- **Aceitar o fluxo como sai do CICFlowMeter e aplicar a limpeza na API:** a API corrigiria as
  taxas infinitas dos fluxos de duração zero e os tempos negativos ([ADR 0006](0006-negativos-e-duracao-zero.md)).
  Exigiria separar das regras de limpeza, que trabalham sobre o dataset inteiro, a parte que vale
  para um fluxo isolado. Fica para quando houver uma fonte de fluxos que não seja o próprio dataset.
- **Receber só os 59 atributos que os modelos usam:** o contrato mudaria a cada modelo (com a porta
  de destino, por exemplo, seriam 60) e os fluxos do dataset não poderiam ser enviados como estão.

## Consequências

- Quem envia fluxos crus precisa aplicar antes as mesmas correções da limpeza. Um fluxo com taxa
  infinita é recusado com 422, em vez de virar um veredito errado.
- Campos como IP de origem ou horário são recusados: não há como um identificador chegar ao modelo
  por engano.
- A API se recusa a subir se um modelo usa atributo fora de `schema.FEATURES` ou se classificador e
  detector estão trocados.
