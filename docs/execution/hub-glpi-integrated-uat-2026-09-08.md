# Hub/GLPI — preparação da homologação integrada — 08/09/2026

## Estado atual: acesso recuperado, dependências acessíveis; F4 não promovida

Após recuperar o acesso SSH, API e worker passaram nos probes autenticados de
GLPI e Zabbix. O Zabbix só voltou a ser acessível após corrigir a rota descrita
abaixo. O ensaio de escrita ainda não foi disparado: falta definir a entidade
GLPI do teste, implantar as correções do worker e verificar todos os canais.

## Registro inicial (anterior à recuperação do SSH)

O usuário autorizou seguir com o ciclo sintético integrado, mantendo WhatsApp
e push desativados. Nenhum alerta, ticket ou mensagem foi gerado nesta etapa.

A conexão do inventário `infra/ansible/inventory/hosts.yml` para
`root@144.91.115.242`, porta 22, usando a cópia local WSL da chave
`id_ed25519_stackvps`, retornou `Permission denied (publickey)`.
Foi solicitada a referência correta de usuário/chave ou alias SSH.
Não foi possível verificar versão implantada, serviços, configurações ou dados
remotos. Nenhum deploy foi executado.

## Pré-check preparado

`infra/scripts/hub-glpi-uat-precheck.py` imprime apenas presença de configuração
e hashes SHA-256 dos arquivos `alerts.py` e `glpi.py`, normalizados para LF.
Executar no diretório do projeto remoto, com o script disponível:

```sh
sudo docker exec -i ninf-api python - < infra/scripts/hub-glpi-uat-precheck.py
sudo docker exec -i ninf-worker-alerts python - < infra/scripts/hub-glpi-uat-precheck.py
```

É inventário de configuração, sem acesso de rede ou escrita no banco. Não é
prova de conectividade, de bloqueio dos canais ou do código já carregado pelo
processo Celery. Comparar os hashes com o checkout testado e conferir o ciclo
de vida do worker antes do ensaio.

Executado localmente com `PYTHONPATH=.` no backend: sem credenciais GLPI,
Zabbix, Gemini ou webhook; sem destinatário WhatsApp; chaves VAPID presentes.
Esses valores não descrevem o servidor. O resultado conserva
`integration_verified=false` e `suppression_verified=false`.

## Condições antes do disparo

1. Confirmar ambiente/tenant de homologação, host e trigger exclusivamente de
   teste e a entidade GLPI correspondente, incluindo políticas de e-mail do
   próprio GLPI e automações externas.
2. Comprovar bloqueio de WhatsApp e push no caminho executado. O worker atual
   decide enviar pela análise IA; severidade baixa no payload não garante
   silêncio. Não remover inscrições de usuários para alcançar esse bloqueio.
3. Verificar credenciais e readiness de GLPI/Zabbix em API e worker, acesso ao
   PostgreSQL/Redis e correspondência do código implantado com o testado.
4. Resolver o contrato de encerramento: `process_ticket_resolution` invoca
   `ZabbixClient.acknowledge_trigger`, enquanto a identidade técnica descrita
   em `zabbix-hub-readonly-integration-2026-09-02.md` permite somente leitura.
   Não ampliar privilégios de produção implicitamente. A resolução local não
   comprova o encerramento remoto; inspecionar também `zabbix_status`.

## Evidências exigidas no ensaio

- Evento real no Zabbix de teste chega à API v1 e à fila `alerts.primary`.
- Um fingerprint corresponde a um incidente persistido e a um único ticket
  GLPI na entidade esperada; IDs e horários registrados sem segredos.
- Reentrega concorrente e falha controlada após criação/reposta perdida
  reutilizam o ticket. A injeção de falha deve ficar restrita ao ensaio.
- Hub exibe o incidente com sessão do tenant correto; outra sessão de tenant
  não consegue consultar o mesmo incidente nem receber seu evento SSE.
- Solução do ticket aciona o webhook GLPI, resolve o incidente local e tem
  resultado remoto no Zabbix comprovado separadamente.
- Auditoria correlacionada e ausência de notificações confirmadas; fechar
  apenas objetos sintéticos criados por esta execução.

## Verificação local desta etapa

```text
pytest -q tests/test_alert_glpi_idempotency.py tests/test_glpi_readiness.py tests/test_glpi_runbook_categories.py
30 passed in 1.09s

ruff check infra/scripts/hub-glpi-uat-precheck.py
All checks passed!
```

O pré-check também foi executado localmente. Esses resultados não substituem
o ensaio integrado. Nenhum código de produto foi alterado nesta etapa.

## Retomada após recuperação do SSH — 08/09/2026

### Rede e acesso

- SSH como root pela chave local `id_ed25519_stackvps` foi comprovado. A opção
  efetiva passou a `PermitRootLogin without-password`; senha continua
  desativada. A alteração foi feita via VNC em
  `/etc/ssh/sshd_config.d/00-ness-nominal-access.conf`, com backup em
  `/root/ssh-access.bak`. Preservar esta recuperação em futuras reconciliações
  de acesso; não reaplicar bloqueio sem provar acesso nominal alternativo.
- API e worker falhavam ao conectar ao Zabbix: erro de socket 113,
  `No route to host`. O hub tinha `144.91.115.242/18` e tentava ARP direto para
  `144.91.72.202`, com vizinho `FAILED`. No Zabbix, o caminho inverso já usava
  o gateway `144.91.64.1`.
- Aplicada exclusivamente a rota `144.91.72.202/32 via 144.91.64.1 dev eth0`.
  A conexão autenticada passou imediatamente, com Zabbix 7.0.27.
- Persistência em `/etc/netplan/60-ness-zabbix-route.yaml`, modo 0600; referência
  versionável em `infra/netplan/60-ness-zabbix-route.yaml`. `netplan generate`
  validou a configuração e `netplan get ethernets.eth0.routes` confirmou o /32.
  Não houve `netplan apply`, restart da rede ou novo reboot. A persistência
  foi validada por configuração, não por reinício do host.
- Warnings do Netplan referem-se ao arquivo anterior `50-cloud-init.yaml`
  (modo 0644 e gateway4/gateway6 depreciados); não foram alterados nesta etapa.
- Rollback da rota: remover somente o arquivo `60-ness-zabbix-route.yaml`,
  executar `netplan generate` e remover a rota /32 com `ip route del`.
  Isso volta a interromper a integração com Zabbix no cenário observado.

### Probes e bloqueios do ensaio

Em API e worker:

```text
GLPI: status=ready mode=dry-run transport=private entities=1 categories=8 writes=0 session_closed=True
Zabbix: status=ready mode=read-only transport=json-rpc version=7.0.27 authenticated=True visible_hosts=1 writes=0
```

- Token GLPI vê a entidade raiz ID 0. Leitura de `/Entity/8` (Cavan) retornou
  HTTP 403. Foi solicitada definição entre manter Cavan com correção de
  permissões ou executar primeiro UAT na raiz. Não houve ampliação de acesso.
- Existe host `10978`, `uat-synthetic-alerts`, com tags `scope=uat` e
  `environment=test`. Trigger `50519`, `UAT: alerta sintético ativo`, valor 0,
  `manual_close=0`, tag `notification=disabled`. Nenhum evento foi gerado.
- A tag de notificação do trigger não é interpretada pelo worker atual.
  Destinatário WhatsApp e ambas as chaves VAPID estão configurados em API e
  worker; a presença de configuração não comprova envio nem supressão.
- `webhook_api_key` está vazio em API e worker. A proteção efetiva da rota de
  ingestão pelo proxy ainda precisa ser verificada antes de considerá-la
  autenticada.
- Hash do `glpi.py` remoto coincide com o checkout anterior:
  `19f6976d5d5f85994eedb2ee5b1726be10c8c75374a0af58fb0d71fd0a1910e9`.
  O `alerts.py` remoto tem hash
  `34f148ed765df70dcb233b0b4aa090b6a2f99ad26c6e4e8a305e72bd8f251d5c`,
  anterior à correção local de retry. API/worker montam o código do host;
  não basta trocar o arquivo para provar o código carregado pelo Celery.

### Controle de canais preparado localmente

Foi adicionado `NINF_ALERT_NOTIFICATIONS_ENABLED` ao worker v1. O padrão
`true` preserva o comportamento existente; `false` impede as chamadas WhatsApp
e Web Push do worker mesmo com urgência HIGH/CRITICAL. Não controla o GLPI,
n8n, outros workers ou inscrições PWA. O pré-check informa a disponibilidade
e o valor da opção; `null` indica versão sem o campo.

O teste reproduziu envio com o controle desativado antes da correção. Depois:

```text
pytest -q: 164 passed in 2.45s
ruff check (quatro arquivos afetados): All checks passed!
black --check (quatro arquivos afetados): 4 files would be left unchanged.
```

Esta alteração de aplicação permanece local, junto das correções de retry;
nenhum deploy foi feito. Houve somente a alteração remota de rota descrita
acima. F4 continua pendente de execução integrada e isolamento de tenant.
