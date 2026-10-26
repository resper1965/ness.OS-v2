# Rollback emergencial do DNS do Zabbix — 02/09/2026

## Sintoma e causa

Usuários reportaram o Zabbix como offline. O registro A público
`zabbix.ness.com.br` apontava para o destino UAT `169.58.234.9`. Esse destino
respondia HTTP 200, mas o corpo era a tela `Database error — No such file or
directory`, e a porta de coleta `10051` estava fechada.

O plano mestre mantinha esse destino em `NO-GO`, com `zabbix-server` mascarado e
sem coleta. Não foi encontrada evidência versionada autorizando o Z-M5. A origem
canônica `144.91.72.202` continuava entregando o login normal e escutando em
`10051`.

## Contenção autorizada

Após autorização explícita, a rotina idempotente
`infra/scripts/cloudflare-zabbix-dns-cutover.sh rollback` alterou somente o
conteúdo do registro A exato:

- antes: `169.58.234.9`;
- depois: `144.91.72.202`;
- proxy Cloudflare: desativado;
- TTL efetivo observado: 300 segundos.

O destino UAT não foi modificado e permanece disponível para diagnóstico.

## Verificação

- API Cloudflare confirmou `144.91.72.202` após a alteração;
- resolvedores `1.1.1.1`, `8.8.8.8` e local retornaram `144.91.72.202`;
- frontend público voltou a entregar o formulário de login normal;
- API pública respondeu Zabbix `7.0.27`;
- `zabbix.ness.com.br:10051` voltou inicialmente a aceitar conexão, mas a
  escuta era de um bridge `socat`, não do `zabbix_server`;
- 20 de 20 requisições HTTPS retornaram HTTP 200.

A verificação da porta isoladamente foi insuficiente. A correção posterior
desativou o bridge, reativou o `zabbix-server` e passou a exigir a comprovação do
proprietário do socket, conforme
`docs/execution/zabbix-source-reactivation-2026-09-02.md`.

## Pendências

- diagnosticar MariaDB/socket e o estado mascarado do `zabbix-server` no destino
  `169.58.234.9` antes de qualquer novo corte;
- exigir GO formal de Z-M5 e evidência pré-corte;
- decidir se `monitoramento.ness.com.br`, atualmente sem resolução DNS, deve ser
  publicado ou removido das configurações de agentes e documentação.
