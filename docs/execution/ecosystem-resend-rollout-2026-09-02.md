# Resend comum ao ecossistema ness.OS — 02/09/2026

## Decisão operacional

O Resend é o provedor transacional comum das aplicações ness.OS. Todos os
remetentes devem pertencer ao domínio verificado `ness.com.br`; cada aplicação
mantém identidade de remetente e testes próprios.

A chave recebida nesta onda pode ser compartilhada somente como bootstrap de
homologação. Ela permanece fora do Git e dos logs. Antes da promoção, a política
alvo é uma chave `Sending access` por aplicação, restrita ao mesmo domínio, para
permitir auditoria e revogação independentes sem trocar de provedor.

Baseline SMTP:

- host: `smtp.resend.com`;
- usuário: `resend`;
- porta: `587`;
- segurança: STARTTLS, sem SSL implícito;
- senha: chave Resend entregue exclusivamente ao segredo runtime.

## Estado por consumidor

| Aplicação | Remetente planejado | Estado em 02/09 | Issue |
|---|---|---|---|
| Psono | `cofre@ness.com.br` | SMTP e envio técnico aprovados; recuperação humana pendente | #44 |
| Authentik | `identidade@ness.com.br` | SMTP e `ak test_email` aprovados; recovery flow pendente | #59 |
| n8n | `noc-alerts@ness.com.br` | credencial criptografada, dois workflows vinculados e envio técnico aprovado; testes funcionais pendentes | #60 |
| GLPI | `suporte@ness.com.br` | SMTP cifrado e envio técnico aprovados; notificações globais permanecem desligadas | #61 |
| Zabbix | `monitoramento@ness.com.br` | media type desabilitado e transporte SMTP aprovado; teste nativo e ativação pendentes no Z-M5 | #62 |
| Hub ness.OS | `hub@ness.com.br` | adapter assíncrono implantado e teste no sink aprovado; gate runtime desligado e eventos não vinculados | #63 |

O épico de controle é a issue #58. MISP, Wazuh e novos consumidores entram
somente após inventário, owner, remetente e caso de uso comprovado.

## Aplicação no Authentik

O contrato versionado foi acrescentado a `app/.env.example` e aos serviços
`authentik-server` e `authentik-worker` de `app/docker-compose.yml`. O runtime
ativo recebeu a chave em `/opt/n-infraops/app/.env`, preservando
`root:root 0600`.

Somente os dois containers Authentik foram recriados. Ambos voltaram saudáveis,
o PostgreSQL preservou seu `StartedAt=2026-08-24T17:30:57.552713526Z` e o comando
oficial `/lifecycle/ak test_email delivered@resend.dev` confirmou o envio.

Rollback root-only:
`/opt/n-infraops/change-backups/authentik-resend-pre-20260902T180436-0300`.

## Aplicação no n8n

O inventário inicial encontrou os workflows ativos `eNLsgPPhK4ReW36t` e
`YziEFpxUu0QgZdUE` com nós `emailSend` sem credencial. A única credencial
anterior era `httpHeaderAuth` da Evolution API.

A credencial `ness.OS Resend SMTP` foi criada pelo comando oficial
`import:credentials`, atribuída ao mesmo projeto proprietário e cifrada pelo
próprio n8n. Uma exportação descriptografada existiu somente em `/tmp` durante
o teste e foi removida imediatamente. O envio a `delivered@resend.dev`, feito
de dentro do container com os campos recuperados do credential store, passou.

Os dois workflows foram reimportados com a referência da credencial, publicados
e confirmados ativos após a recriação exclusiva de `ninf-n8n`. Os exports no Git
registram apenas ID, nome e tipo da dependência, nunca senha. Remetente e
destinatário padrão também foram explicitados no contrato de ambiente.

Rollback root-only aprovado para a mudança final:
`/opt/n-infraops/change-backups/n8n-resend-pre-20260902T182040-0300`.

Duas tentativas anteriores foram revertidas automaticamente e preservadas para
auditoria em `n8n-resend-pre-20260902T181503-0300` e
`n8n-resend-pre-20260902T181733-0300`. A primeira comprovou que
`--activeState=fromJson` não é suportado no deployment regular; a segunda
isolou o conflito do Task Broker no executor CLI. Nenhuma delas deixou
credencial ou vínculo residual.

## Aplicação no GLPI

O GLPI 11.0.8 estava com `use_notifications=0`, `smtp_mode=0`, transporte vazio
e fila zerada. O transporte Resend foi gravado pela API de configuração do
próprio GLPI; `smtp_passwd` foi cifrado pelo `GLPIKey`. O kernel reabriu a
configuração, validou todos os campos sem imprimir a chave e enviou a mensagem
de teste para `delivered@resend.dev`.

O remetente é `suporte@ness.com.br`. As notificações globais continuam
desligadas para impedir disparos reais antes da revisão de templates,
destinatários, entidades e fila. Rollback root-only:
`/opt/n-infraops/change-backups/glpi-resend-pre-20260902T183329-0300`.

Tentativas intermediárias que falharam antes da persistência final ou foram
revertidas ficam registradas como evidência de hardening do procedimento: a
imagem bloqueia `chown` do arquivo copiado para `/tmp`, o bootstrap PHP por stdin
não carrega o kernel completo e o prompt oculto de `config:set` é incompatível
com o argumento obrigatório nesta versão. O domínio canônico validado é
`n-ticket.ness.com.br`, não `glpi.ness.com.br`.

## Aplicação no Zabbix

O destino UAT `zbx-prd-01` executa o frontend Zabbix 7.0.27 com o processo
`zabbix-server` ausente/inativo e a porta 10051 fechada. Antes e depois da
mudança havia zero ações, media types e conectores ativos.

O media type `ness.OS Resend SMTP` foi criado como ID `72`, com remetente
`monitoramento@ness.com.br`, STARTTLS na porta 587, validação de certificado e
autenticação por senha. Ele permanece desabilitado, sem associação a usuários
ou operações de ações. Um envio SMTP controlado do próprio host para
`delivered@resend.dev` comprovou DNS, TLS, autenticação e aceitação pelo Resend.

O teste nativo do Zabbix não foi forçado nesta etapa: a implementação 7.0.27
recusa testar media type desabilitado e encaminha o teste pelo processo
`zabbix-server`. Habilitar a mídia ou iniciar o servidor quebraria o isolamento
Z-M3. Esse teste, os templates de problema/recuperação e a ativação ficam no
gate Z-M5 da issue #62.

Rollback e evidência root-only:
`/var/lib/ness-os/change-backups/zabbix-resend-pre-20260902T184636-0300`.

## Aplicação no Hub ness.OS

O backend recebeu um adapter assíncrono para a API HTTP do Resend, reutilizando
o `httpx` já existente. O contrato exige chave de idempotência por mensagem,
aplica timeout, limita tentativas, repete somente falhas transitórias e mantém
contadores de entrega. Logs registram apenas um hash de correlação; destinatário,
assunto, conteúdo, resposta do provedor e chave não são registrados.

O runtime usa `hub@ness.com.br`, mas permanece fail-closed com
`NINF_TRANSACTIONAL_EMAIL_ENABLED=false`. Cinco testes unitários passaram no
mesmo ambiente Python da aplicação. Após a implantação, a API voltou saudável,
o gate bloqueou uma tentativa antes da rede e um processo técnico separado
enviou uma única mensagem para `delivered@resend.dev` com idempotência; o Resend
aceitou na primeira tentativa. Nenhum evento ou destinatário real foi conectado.

Convites e recuperação continuam sob responsabilidade do Authentik. Incidentes
e relatórios continuam sob responsabilidade dos workflows n8n já ativos. A
issue #63 permanece aberta para decidir fontes de verdade, templates, escopo por
tenant, opt-out aplicável e tratamento dos webhooks de bounce/delivery antes de
qualquer ativação do Hub.

Rollback e evidência root-only:
`/opt/n-infraops/change-backups/hub-resend-pre-20260902T191347-0300`.

## Gates restantes

1. executar recuperação com conta autorizada no Psono e no Authentik;
2. confirmar expiração, uso único, auditoria e falha do provedor;
3. executar o teste nativo, revisar templates e ativar o Zabbix somente no Z-M5;
4. decidir a fonte de verdade dos eventos do Hub e homologar webhooks do Resend;
5. segregar e rotacionar a chave temporária antes da promoção;
6. migrar os segredos runtime para o cofre após recovery e restore do Psono.
