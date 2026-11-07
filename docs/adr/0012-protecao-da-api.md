---
status: aceita
data: 2026-11-06
---

# Chave de acesso e limite de requisições opcionais; métricas abertas na rede interna

A API ganha três peças de operação. Uma chave de acesso (`NIDS_API_KEY`, enviada no cabeçalho
`X-API-Key`) protege `/predict` e `/model`. Um limite de requisições por minuto, por cliente
(`NIDS_RATE_LIMIT`), responde 429 a quem passar dele. E `/metrics`, no formato do Prometheus, conta
os vereditos por tipo e mede a latência do `/predict`.

A chave e o limite ficam **desligados por padrão**. Com eles ligados, a demonstração local, o
exemplo do README e quem visita o repositório precisariam de configuração extra antes do primeiro
teste. O README diz que os dois devem ser ligados antes de a API ficar acessível fora da máquina.
`/health` e `/metrics` ficam abertos, como é comum para verificação de saúde e coleta de métricas
dentro da rede.

## Opções consideradas

- **Ligados por padrão, com uma chave gerada na subida:** mais seguro, mas a chave precisaria ser
  lida no log e repassada ao replay e ao exemplo do README.
- **Uma biblioteca de limite de requisições (slowapi):** guarda o estado em Redis e serve a vários
  processos, mas é uma dependência a mais para um serviço de um processo só.

## Consequências

- O limite vive na memória do processo: com vários processos (ou réplicas), cada um conta o seu.
- A chave é comparada em tempo constante e guardada como `SecretStr`, que não aparece em logs.
- `nids replay` aceita `--api-key` (ou `NIDS_API_KEY`) para falar com uma API protegida.
