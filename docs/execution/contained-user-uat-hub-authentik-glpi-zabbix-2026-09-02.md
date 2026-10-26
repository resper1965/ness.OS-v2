# Homologação contida de usuários — Hub, Authentik, GLPI e Zabbix

Data: 2026-09-02

Escopo: autenticação, autorização, tenant/entidade, logout, revogação e contingência em UAT.

Fora do escopo: produção, deploy, mudança de código, JIT no Zabbix, GLPI Agent, alertas, coleta, ações, notificações e limpeza de providers legados.

## Resultado esperado e limite de segurança

Um facilitador executa primeiro os prechecks e perfis descartáveis. Os participantes
nominais entram depois, um por vez, em sessões de 10–15 minutos que podem ocorrer em
janelas diferentes. A primeira janela exige somente um administrador; operador e
cliente podem ser homologados posteriormente sem bloquear o trabalho automatizado.
A homologação é somente leitura: usa objetos fictícios já preparados, não reconhece
problemas, não abre chamados, não altera configuração e não inicia o `zabbix-server`.

O estado abaixo vem do repositório e deve ser confirmado pelo precheck; não é evidência do ambiente atual:

| Componente | Fluxo a testar | Estado documentado |
| --- | --- | --- |
| Authentik | identidade central, grupos e MFA | baseline de grupos existe; acesso externo exige aprovação e grupo próprio por aplicação |
| Hub | OIDC authorization code + PKCE S256; JIT local | implementação local usa cookie host-only `Secure`, `HttpOnly`, `SameSite=Strict`, valida `Origin` em mutações e não envia JWT ao JavaScript/SSE; ainda exige deploy e prova no navegador antes de promover |
| GLPI 11.0.8 | `forward_auth` temporário + usuário preexistente/plugin | parcial; entidade, logout, revogação, spoofing de cabeçalho e acesso direto ainda precisam de prova |
| Zabbix UAT | SAML; usuário preexistente | login ponta a ponta já observado; JIT/SCIM e SLO estão desligados; `zabbix-server` deve continuar `inactive/masked` |

Um login positivo isolado nunca é suficiente para `GO`.

## Donos e preparação única (T-30 a T-10)

- **Facilitador:** executa prechecks, abre/fecha a janela, altera apenas contas/grupos descartáveis e consolida evidências.
- **Observador:** acompanha os testes negativos e declara `GO/NO-GO`; não recebe senha nem código MFA.
- **Participantes:** administrador nominal, operador nominal e representante de cliente/tenant A. Cada pessoa usa sessão privada e seu próprio MFA.

Preparar antes da janela dois tenants/entidades fictícios, `UAT-A` e `UAT-B`, cada um com um objeto inofensivo e facilmente reconhecível no Hub e GLPI. No Zabbix, usar host groups de UAT já existentes; não criar hosts nem ligar coleta durante a homologação.

Criar ou reconciliar pela interface/API suportada, nunca por SQL, as identidades descartáveis abaixo. Usar aliases sem nome de cliente real e validade máxima de 24 horas. Senhas, tokens, QR codes e códigos de recuperação ficam somente no cofre/canal individual.

## Matriz mínima de perfis

| Identidade | Authentik | Hub | GLPI | Zabbix UAT | Resultado mínimo |
| --- | --- | --- | --- | --- | --- |
| `UAT-ADM-NOM` | somente `platform_admin`/alias aprovado e grupos explícitos das aplicações; MFA | `platform_admin` | perfil administrativo nominal aprovado | papel administrativo nominal aprovado, sem JIT | entra nas quatro aplicações; operações globais de leitura disponíveis; MFA registrado |
| `UAT-OP-NOM` | `noc` **ou** `soc`, nunca ambos por conveniência; grupos das aplicações; MFA se exigido | `noc` ou `soc` | `Observer` na entidade/grupos operacionais autorizados | `User role` limitado aos host groups de UAT | lê o escopo operacional; não administra plataforma, identidades ou autenticação |
| `UAT-CLI-A` | `usuarios`, `tenant_id=UAT-A`, grupos Hub/GLPI | `cliente`, tenant `UAT-A` | `Self-Service` somente na entidade `UAT-A` | acesso negado, salvo papel de cliente explicitamente aprovado antes da janela | vê somente `UAT-A`; recebe 403/negativa equivalente para `UAT-B` e funções globais |
| `UAT-CLI-B` | `usuarios`, `tenant_id=UAT-B`; conta auxiliar | `cliente`, tenant `UAT-B` | `Self-Service` somente em `UAT-B` | negado | fornece o objeto-alvo para o teste cross-tenant; não requer participante dedicado |
| `UAT-DESAT` | conta descartável, grupo mínimo; depois `inactive` | sem nova sessão e sessão anterior rejeitada no prazo aceito | sem nova sessão e sessão anterior revogada no prazo aceito | sem nova sessão; usuário local colocado no grupo `Disabled` se necessário | prova desprovisionamento; se a aplicação não suportar revogação imediata, registrar TTL e tratar como `NO-GO` até decisão de risco |

Grupo desconhecido/sem grupo deve resultar em negação na borda de cada aplicação. No Hub, o fallback técnico atual para `cliente` exige também `tenant_id`; sem tenant, endpoints tenant-scoped devem negar acesso.

## Gate A — prechecks automatizados (T-10 a T-3)

Executar primeiro fora de qualquer sistema real, a partir da raiz do repositório:

```bash
bash infra/tests/test-authentik-readiness.sh
bash infra/scripts/hub-session-readiness.sh
cd app/backend
pytest -q \
  tests/test_browser_session_security.py \
  tests/test_oidc_pkce.py \
  tests/test_authentik_rbac.py \
  tests/test_core_auth.py \
  tests/test_tenant_secops_auth.py \
  tests/test_dashboard_auth.py
```

Baseline local em 2026-09-02: gates estáticos de Authentik e sessão do Hub em `PASS`, além de `49 passed`. Qualquer regressão é `NO-GO` antes do teste humano.

Reexecução em 02/09/2026 confirmou os mesmos `49 passed` e os dois gates
estáticos. O precheck público sem sessão registrou:

| Alvo | Resultado |
| --- | --- |
| Authentik | HTTP 200 |
| Hub | HTTP 200 |
| GLPI | HTTP 302 para `sso.ness.com.br` |
| n8n | HTTP 302 para `sso.ness.com.br` |
| GLPI com `Remote-User`/`X-Authentik-Username` forjados | continuou HTTP 302 para o Authentik; nenhuma sessão criada |
| Zabbix UAT | inicialmente falhou por banco indisponível; após recuperação operacional, `/zabbix/index_sso.php` retornou HTTP 302 para o Authentik |

A rota Zabbix correta inclui o prefixo `/zabbix/`; o exemplo abaixo foi
reconciliado. O incidente e a recuperação estão em
`zabbix-uat-unattended-upgrade-recovery-2026-09-02.md` e nas issues #56/#57.

No runner autorizado de UAT, com `set +x` e credenciais injetadas pelo cofre sem impressão:

```bash
RUN_ID="$(date +%Y%m%dT%H%M%S%z)"
export AUTHENTIK_URL='https://sso.ness.com.br'
# AUTHENTIK_TOKEN deve ser injetado pelo runner, nunca digitado na linha de comando.
bash infra/scripts/authentik-readiness-report.sh > "authentik-readiness-${RUN_ID}.txt"

# Conta UAT descartável e segredo devem vir do cofre/runner.
HUB_SESSION_EXECUTE=1 \
  bash infra/scripts/hub-session-readiness.sh --execute-contained \
  > "hub-session-readiness-${RUN_ID}.txt"

bash infra/scripts/authentik-public-precheck.sh \
  > "authentik-public-precheck-${RUN_ID}.txt"

for url in \
  'https://sso.ness.com.br/-/health/live/' \
  'https://hub.ness.com.br/' \
  'https://n-ticket.ness.com.br/' \
  'https://zabbix-uat.ness.com.br/zabbix/index_sso.php'; do
  curl --silent --show-error --output /dev/null \
    --connect-timeout 5 --max-time 15 \
    --write-out '%{url_effective} %{http_code}\n' "$url"
done > "http-precheck-${RUN_ID}.txt"
```

Aceitar somente: Authentik e Hub saudáveis; GLPI e Zabbix respondendo com o status esperado do fluxo (`200` ou redirecionamento controlado), sem `5xx`, loop ou domínio inesperado. O relatório Authentik deve retornar `core_health=PASS`, exatamente uma aplicação canônica por slug e os grupos esperados. Contagem ambígua de aplicação/provider bloqueia a janela; não limpar legado durante o teste.

No host Zabbix UAT, registrar apenas o resumo abaixo; não executar o relatório completo fora do repositório restrito porque ele contém nomes de usuários:

```bash
systemctl is-active zabbix-server || true
systemctl is-enabled zabbix-server || true
ss -lntH 'sport = :10051'
```

Saída obrigatória: `inactive`, `masked` e nenhuma linha para TCP/10051. Confirmar também que actions, media types e connectors de teste permanecem inativos. Se qualquer canal puder disparar efeito real, `NO-GO` imediato.

Checklist automático/manual de entrada:

- [ ] relógios sincronizados e janela/owner registrados;
- [ ] export/backup restrito e recente de Authentik, GLPI e configuração/banco de acesso Zabbix disponível para rollback;
- [ ] `UAT-A` e `UAT-B` contêm apenas dados fictícios;
- [ ] conta break-glass local testada em sessão separada, sem usar o IdP, e imediatamente encerrada;
- [ ] nenhum participante conhece a credencial break-glass;
- [ ] captura de HAR completa e impressão de headers/cookies estão desativadas.

## Execução humana — 10–15 minutos por participante

Cada participante usa um navegador/perfil privado distinto. O facilitador marca `PASS`, `FAIL` ou `N/A justificado` na tabela final; não pede compartilhamento de tela durante digitação de senha/MFA.

### Administrador nominal — 12 minutos

| Minuto | Ação | Aceite |
| --- | --- | --- |
| 0–2 | abrir o portal Authentik, autenticar e cumprir MFA | identidade nominal e evento de MFA, sem conta compartilhada |
| 2–5 | abrir Hub pelo catálogo e consultar uma tela global somente leitura | papel `platform_admin`; tenant não é inferido indevidamente |
| 5–8 | abrir GLPI e consultar perfil/entidades, sem salvar | perfil nominal aprovado; entidades esperadas, sem duplicata inesperada |
| 8–10 | abrir Zabbix pelo SAML e consultar papel/host groups | usuário preexistente correto; nenhuma permissão de escrita fora do papel aprovado |
| 10–12 | sair de cada aplicação e do IdP; tentar voltar pelo histórico | sessão encerrada ou autenticação novamente exigida conforme política |

Teste negativo do administrador: uma identidade `admin` local/de aplicação não pode acessar função exclusiva de `platform_admin`. Não executar uma mutação para provar isso; use endpoint/tela global somente leitura.

### Operador — 12 minutos

| Minuto | Ação | Aceite |
| --- | --- | --- |
| 0–2 | login Authentik e, se aplicável, MFA | identidade nominal; somente `noc` ou `soc` |
| 2–5 | Hub: consultar dashboard/tenant explícito de UAT | leitura operacional funciona; administração global retorna 403/oculta com bloqueio server-side |
| 5–8 | GLPI: consultar objetos das entidades autorizadas e abrir perfil | `Observer`; sem configuração, usuário ou entidade não atribuída |
| 8–10 | Zabbix: consultar host group UAT e papel | leitura/ack conforme papel; sem Administration, scripts ou outro host group |
| 10–12 | logout e reentrada pelo catálogo | logout previsível; novo login preserva o mesmo papel mínimo |

Se o operador possui autorização multi-tenant por função, isso deve constar no caso de teste; nesse perfil, acesso explícito a outro tenant não é teste negativo válido. A negativa obrigatória continua sendo administração global/identidade.

### Cliente/tenant A — 12 minutos

| Minuto | Ação | Aceite |
| --- | --- | --- |
| 0–3 | login e Hub: abrir resumo de `UAT-A` | papel `cliente`; somente dados fictícios de `UAT-A` |
| 3–6 | Hub: trocar URL/parâmetro para `UAT-B` e tentar endpoint/tela global | 403/negativa server-side; nenhum nome, contagem ou dado de `UAT-B` |
| 6–9 | GLPI: localizar objeto de `UAT-A`; tentar link direto do objeto conhecido de `UAT-B` | `UAT-A` visível; `UAT-B` negado sem metadado lateral |
| 9–10 | tentar abrir Zabbix pelo catálogo e URL direta | negado, salvo autorização de cliente documentada antes da janela |
| 10–12 | logout; usar voltar/recarregar | conteúdo protegido não reaparece sem autenticação |

## Testes negativos dirigidos (facilitador, 8–10 minutos)

Executar em sequência, sem brute force e sem alterar objetos:

1. **Sem sessão:** abrir uma URL protegida do Hub, GLPI e Zabbix; esperar `401/403` ou redirecionamento ao IdP.
2. **Sem grupo:** usar conta descartável ativa sem grupo de aplicação; o Authentik deve negar a aplicação. No Hub, confirmar que fallback para `cliente` sem `tenant_id` não libera dado tenant-scoped.
3. **Cross-tenant:** repetir os acessos de `UAT-CLI-A` ao ID/URL conhecido de `UAT-B`; aceitar somente negativa sem conteúdo, contagem, nome ou cache do outro tenant.
4. **Cabeçalho GLPI:** a partir da borda pública, enviar valores falsos de `Remote-User`/`X-Authentik-Username`; o proxy deve remover/substituir e nunca autenticar o valor fornecido. Não testar acesso direto ao backend a partir de rede não autorizada; validar por probe controlado do runner.
5. **OIDC Hub:** iniciar um login e alterar/remover `state`, reutilizar callback ou deixar o verifier ausente; esperar falha sem criar sessão. Nunca registrar `code`, token ou verifier.
6. **Desativação:** autenticar `UAT-DESAT`, desativá-la no Authentik, revogar suas sessões/conexões e colocá-la no grupo local `Disabled` do Zabbix quando aplicável. Uma sessão privada nova deve falhar nas quatro aplicações. Recarregar a sessão antiga até o prazo máximo aprovado; acesso além desse prazo é `NO-GO`.
7. **Break-glass:** simular indisponibilidade do IdP sem derrubá-lo, usando somente a rota local/restrita documentada. Uma conta local administrativa funciona; contas locais cotidianas não são aceitas como contingência.

Zabbix não possui SLO configurado e GLPI usa proxy temporário. Se o logout não encerrar IdP e aplicação, registrar `FAIL`; não mascarar como limitação conhecida. O observador decide `NO-GO` ou exceção formal com prazo, owner e compensação.

## Evidência mínima, sem segredos

Criar um único registro restrito de homologação com `RUN_ID`, horário BRT, ambiente, commit do repositório, facilitador, observador e versão declarada de cada aplicação. Anexar somente:

1. saída dos prechecks, removendo nomes/e-mails desnecessários;
2. uma captura pós-login por perfil mostrando aplicação e papel/escopo, com e-mail, nome de cliente, hostname/IP e dados pessoais mascarados;
3. status HTTP e identificador do caso para cada negativa (`401/403/redirect`), nunca request/response headers completos;
4. metadados de auditoria Authentik/ aplicação: horário, alias UAT, aplicação, resultado e event ID; sem claims, assertion SAML, JWT, cookie ou IP pessoal;
5. tabela final abaixo e hash dos anexos sanitizados.

Nunca anexar HAR bruto, URL de callback completa, `Authorization`, `Set-Cookie`, QR/MFA, código de recuperação, segredo OIDC, token GLPI/Zabbix, dump ou log integral. Se um segredo aparecer, interromper a coleta, restringir o artefato, rotacionar/revogar o valor e gerar nova evidência sanitizada.

| Caso | Authentik | Hub | GLPI | Zabbix | Evidência/observação |
| --- | --- | --- | --- | --- | --- |
| administrador + MFA + papel |  |  |  |  |  |
| operador + menor privilégio |  |  |  |  |  |
| cliente `UAT-A` |  |  |  |  |  |
| sem sessão/sem grupo |  |  |  |  |  |
| cross-tenant `A → B` | N/A |  |  | conforme política |  |
| logout/reentrada |  |  |  |  |  |
| desativação/revogação |  |  |  |  |  |
| break-glass sem IdP |  | conforme desenho |  |  |  |

## Critério GO/NO-GO

Declarar `GO` somente para a aplicação que cumprir todos os itens aplicáveis:

- prechecks verdes e fluxo canônico único identificado;
- administrador nominal com MFA e operador/cliente com menor privilégio;
- autorização efetiva no servidor, não apenas menus ocultos;
- zero exposição cross-tenant em Hub e GLPI, inclusive link direto e cache;
- conta sem grupo e conta desativada negadas; sessão revogada dentro do prazo aprovado;
- logout e expiração conformes; trilha de auditoria identifica alias, app, resultado e horário;
- break-glass local testado e restrito, sem torná-lo conta cotidiana;
- Zabbix permanece `inactive/masked`, sem listener 10051 e sem canais ativos;
- nenhuma evidência contém segredo ou dado real de cliente.

É `NO-GO` imediato para a aplicação afetada se houver acesso cross-tenant, elevação de papel, header spoofing, callback OIDC aceito com `state`/PKCE inválido, usuário desativado obtendo nova sessão, ausência de recuperação administrativa, efeito real em ticket/monitoramento/notificação ou vazamento de segredo. Falha de logout/revogação, duplicata de identidade/perfil ou divergência entre grupo e papel também bloqueia promoção até correção ou exceção formal aprovada.

O resultado global é `GO` apenas quando as quatro aplicações estão `GO`. Caso contrário, registrar `NO-GO parcial`, manter somente as aplicações já aprovadas e não ampliar público/tenant. Em particular, a sessão segura do Hub precisa ser comprovada após deploy (atributos do cookie, ausência de token na URL/armazenamento e logout), enquanto a ausência de SLO do Zabbix e o `forward_auth` temporário do GLPI continuam gates explícitos a observar, não itens implicitamente aceitos.

## Sessão segura do hub implantada — 02/09/2026 17:50–18:06 BRT

O inventário inicial confirmou que a produção ainda usava JWT no
`localStorage`, token na URL do SSE, não possuía `/api/auth/logout` e divergira
dos fontes já aprovados por 49 testes. O pacote mínimo foi construído sem
alteração de banco e com rollback de fonte, Compose, Caddyfile e imagem do
frontend.

Dois mecanismos de proteção impediram promoção incompleta antes do aceite:

1. o import na imagem produtiva encontrou incompatibilidade da versão de
   FastAPI com uma rota 204 que inferia corpo; a rota passou a declarar
   `response_model=None` e retornar explicitamente `Response`, mantendo o
   cookie expirado;
2. o primeiro reload após a correção carregou um bind mount antigo do
   Caddyfile, pois o tar havia trocado o inode. A tentativa foi revertida e o
   deploy final recriou somente o proxy para remontar o arquivo persistente.

O deploy final foi aprovado com:

- API e frontend saudáveis; Caddy ativo e hash do arquivo montado igual ao
  arquivo persistente;
- `/api/auth/me` sem sessão: 401 e `Cache-Control: no-store`;
- `/api/auth/logout` sem origem confiável: 403;
- logout com origem `https://hub.ness.com.br`: 204 e expiração de cookie
  `HttpOnly`, `Secure`, host-only e `SameSite=Strict`;
- SSE sem sessão: 401; nenhum `ninf_token` ou `stream?token=` no bundle;
- tela pública renderizada em 2,26 s, sem cookie nem token em `localStorage`;
- botão SSO redirecionando ao Authentik com `state`, `response_type=code`,
  `code_challenge` e `code_challenge_method=S256`, sem autenticar usuário;
- precheck público posterior aprovado para Authentik, hub, GLPI, n8n, Zabbix
  UAT e tentativa GLPI com cabeçalhos de identidade forjados.

Rollback e evidências restritas estão em
`/opt/n-infraops/rollback/hub-session-20260902T1805-0300`. O login nominal,
callback OIDC, logout do IdP e revogação ainda dependem da janela contida e não
foram inferidos a partir desses testes sem sessão.

O achado separado da F4 no módulo `contabo_firewall.py` foi corrigido e
implantado às 18:52 BRT. Além do fechamento da string multilinha, o contrato foi
alinhado à API vigente: `PUT /v1/firewalls/{id}`, corpo `rules.inbound`,
`destPorts` serializado e `x-request-id` UUID. Nove testes focados passaram; a
compilação e o import em produção foram aprovados. O roteador mutável continua
fora da aplicação e nenhuma chamada externa foi executada. Rollback:
`/opt/n-infraops/rollback/contabo-firewall-module-20260902T185146-0300-retry1`.

### Leitura Zabbix pelo hub

Às 19:21 BRT, o hub passou a usar a identidade técnica
`svc_ninfraops_api`, sem interface e com allowlist de oito métodos somente de
leitura. A prova negativa recusou `token.get`; as provas positivas retornaram
Zabbix 7.0.27 e uma amostra de host, sempre com zero escritas. O readiness do
GLPI permaneceu aprovado e o hub respondeu HTTP 200.

Depois do aceite, o token pessoal de cutover foi desativado e o readiness foi
repetido com sucesso. O segredo técnico fica em arquivo externo ao Git,
`root:root` `0600`; a duplicata anterior em `.env` e os estágios temporários de
transporte foram removidos. Detalhes e evidências estão em
`zabbix-hub-readonly-integration-2026-09-02.md`. Isso não aprova ainda o fluxo
de incidente, deduplicação ou escrita no GLPI.

### Transporte SMTP do Authentik

O runtime ativo já contém as variáveis SMTP/Resend e ambos os contêineres do
Authentik estão saudáveis, sem reinícios. Uma conexão iniciada dentro do
servidor autenticou com STARTTLS na porta 587 e encerrou sem transmitir
mensagem: `authentik_smtp_auth_without_send=PASS` e
`authentik_smtp_message_sent=no`.

Esse resultado valida somente o transporte. Ativação, recuperação, conteúdo da
mensagem, expiração/reuso do link e auditoria continuam fora do aceite até um
destinatário controlado executar a jornada completa.

## Integração privada do GLPI — 02/09/2026 18:29–18:38 BRT

O erro `ERROR_WRONG_APP_TOKEN_PARAMETER` foi reproduzido e não indicava token
revogado. O GLPI filtra primeiro os clientes de API pelo endereço de origem; o
cliente técnico aceitava somente o IP público da VPS, enquanto o Hub nasce no
subnet Docker `172.18.0.0/16`. O token protegido local foi comparado em memória
com o valor vigente e coincidiu, sem exposição ou rotação.

O filtro do cliente ID 2 foi alterado pela camada de modelo do GLPI para o
subnet interno. O Hub passou a receber as credenciais por arquivo `root:root`
`0600`, fora do Git, e a usar `http://ninf-glpi/apirest.php`. A prova posterior
retornou `status=ready`, transporte privado, uma entidade, zero escritas e
sessão encerrada. O proxy público do GLPI permanece sob Authentik.

Com o manifesto aprovado, o dry-run encontrou oito categorias ausentes; o
apply criou exatamente oito e a repetição encontrou zero pendências. A
categoria de operação interna foi reconciliada para `ness.` sem conceder ao
usuário técnico direito permanente de atualização. Isso conclui apenas API e
taxonomia; isolamento entre entidades, inventário e jornada de ticket ainda
permanecem como gates da F3.

## Rollback e encerramento (máximo 15 minutos)

Ao primeiro critério de `NO-GO`, parar novos logins e não tentar corrigir durante a homologação.

1. desativar `UAT-ADM-NOM`, `UAT-OP-NOM`, `UAT-CLI-A`, `UAT-CLI-B` e `UAT-DESAT`; remover grupos de aplicação e revogar sessões/conexões no Authentik;
2. no Hub, revogar sessões/JWTs conforme o mecanismo vigente e desativar os usuários JIT descartáveis; se não existir revogação direcionada, manter `NO-GO` e escalar — esta janela não autoriza rotação global do segredo JWT; não excluir usuários se isso apagar auditoria;
3. no GLPI, desativar as contas UAT e restaurar somente bindings/perfis alterados a partir do export aprovado; preservar histórico e nunca usar SQL ad hoc;
4. no Zabbix, colocar as contas UAT no grupo `Disabled`, invalidar sessões e restaurar configuração de autenticação/grupos do dump restrito se houve alteração; confirmar novamente `inactive`, `masked`, porta 10051 fechada e canais inativos;
5. se o fluxo SSO foi afetado, reativar o provider anterior preservado apenas pelo procedimento aprovado; não apagar o provider atual na mesma janela;
6. repetir os probes sem sessão, registrar `rollback=PASS|FAIL`, owner da correção e próximo gate. `rollback=FAIL` exige escalonamento e mantém `NO-GO`.

Encerrar removendo os dados fictícios somente pelo processo suportado e após preservar a evidência necessária. A exclusão das identidades pode ocorrer depois da retenção de auditoria; desativação imediata é suficiente para fechar a janela.

## Fontes locais inspecionadas

- `config/authentik/ness-os-baseline.yaml`
- `docs/adr/0007-authentik-central-identity.md`
- `docs/adr/0013-platform-administration-boundary.md`
- `infra/docs/authentik-integration-audit.md`
- `docs/execution/authentik-google-external-approval-2026-09-01.md`
- `docs/execution/zabbix-uat-saml-2026-08-26.md`
- `docs/execution/zabbix-uat-access-baseline-2026-08-26.md`
- `docs/execution/glpi-foundation-2026-08-21.md`
- `app/backend/app/api/routers/auth.py`
- `app/backend/app/core/dependencies.py`
- `app/frontend/src/hooks/useAuth.tsx`
- testes focados de OIDC, RBAC, autenticação e tenant em `app/backend/tests/`
