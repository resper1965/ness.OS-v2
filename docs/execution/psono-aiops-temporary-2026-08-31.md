# Psono Community — implantação temporária na AIOps

> Executado em 31/08/2026. Esta é uma colocação temporária e reversível dentro
> do ecossistema Contabo; não substitui a VPS dedicada prevista para produção.

## Estado implantado

- domínio: `cofre.ness.com.br`;
- destino DNS: `144.91.115.242`, registro A DNS-only;
- host: VPS AIOps `vmi3409271`;
- stack: `/opt/ness-os-psono`;
- segredos estáveis: `/etc/ness-os/psono.env`, `root:root 0600`;
- contêineres: `ness-psono` e `ness-psono-db`;
- PostgreSQL exclusivo, sem porta publicada;
- Psono limitado a 2 CPU/2 GiB e PostgreSQL a 1 CPU/1 GiB;
- acesso do Caddy ao Psono pela rede externa `app_ninf-net`;
- Caddy anterior preservado em
  `/opt/n-infraops/app/Caddyfile.pre-psono-20260831T165739-0300`.

O registro legado `vault.ness.com.br`, que apontava para o IP Microsoft não
inventariado `191.234.169.182`, foi removido depois do aceite HTTPS do novo
domínio.

## Controles de entrada

- `ALLOW_REGISTRATION: false`;
- `ALLOW_LOST_PASSWORD: false`;
- administração habilitada;
- uma conta bootstrap nominal `resper@ness.com.br`;
- credencial bootstrap entregue somente em
  `/home/resper/.secrets/psono-bootstrap-credentials`, modo `0600`;
- SMTP desabilitado enquanto não houver chave Resend válida.

O Psono CE usa autenticação nativa. A ausência de SSO/LDAP e auditoria granular
continua sendo uma limitação aceita da PoC, não uma funcionalidade pendente do
proxy.

## Evidência de recuperação

- timer `ness-psono-backup.timer` habilitado e ativo, execução diária às 01:30
  `America/Sao_Paulo`, com atraso aleatório de até 10 minutos;
- repositório Restic dedicado:
  `ness-os/psono-prod/psono` no Object Storage configurado;
- snapshot final desta implantação: `36d79c6d`;
- SHA-256 do dump e pacote de configuração: aprovado;
- `restic check`: aprovado, dois snapshots e nenhum erro;
- restore isolado e validação de `pg_restore`: `psono_restore_verify=PASS`.

## Rollback sem perda de dados

1. remover somente o registro A `cofre.ness.com.br`;
2. restaurar o backup de Caddy registrado acima e executar `caddy reload`;
3. parar `ness-psono` e `ness-psono-db` sem remover volumes;
4. preservar `/etc/ness-os/psono.env`, o volume PostgreSQL e o último snapshot
   Restic até a decisão formal.

## Saída para VPS Contabo dedicada

1. executar novo backup e restore isolado;
2. provisionar a stack dedicada com as mesmas chaves estáveis;
3. restaurar o dump PostgreSQL e validar login com segredos de teste;
4. mudar o registro A após healthcheck/TLS;
5. observar a nova VPS antes de parar a stack temporária;
6. remover a colocação na AIOps somente por autorização separada.

## Pendências para promoção

- fornecer chave Resend e homologar ativação, recuperação e notificações;
- concluir o primeiro acesso e provar recuperação independente do segundo
  custodian, Ismael Araujo (`iaraujo@ness.com.br`);
- exigir MFA nas contas operacionais;
- executar os cenários completos de compartilhamento, revogação, recovery code,
  emergency code e clientes móveis definidos na PoC.

## Revalidação operacional em 01/09/2026

- `https://cofre.ness.com.br/` e `/server/info/`: HTTP 200, HSTS e Psono CE
  `7.3.6`;
- `ness-psono` e `ness-psono-db`: saudáveis, com os mesmos digests fixados no
  repositório;
- cadastro e recuperação de senha: desabilitados no servidor e no cliente;
- host: Debian 12, NTP sincronizado, root remoto e senha SSH bloqueados, UFW e
  Fail2ban ativos;
- arquivos de runtime: `/etc/ness-os/psono.env` e
  `/etc/ness-os/backup-s3.env` em `0600 root:root`;
- backup `20260901T013652-0300`: `psono_backup=PASS`, sem erro no `restic
  check`; timer ativo para a próxima execução;
- MFA ainda não ativado nas contas (`multifactor_enabled: false`), portanto o
  cofre continua sem autorização para receber credenciais reais.

## Segundo custodian em 01/09/2026

- Ismael Araujo (`iaraujo@ness.com.br`) formalizado como segundo responsável;
- conta nominal criada pelo comando administrativo suportado, promovida a
  `superuser` e marcada para troca obrigatória de senha no primeiro acesso;
- credencial bootstrap preservada somente em
  `/home/resper/.secrets/psono-ismael-bootstrap-credentials`, modo `0600`;
- staging remoto removido após comparação de hash da transferência;
- durante a primeira validação local, o PowerShell expandiu indevidamente o
  conteúdo da credencial no retorno da ferramenta. A conta ainda não havia
  sido acessada: ela foi excluída e recriada imediatamente com nova senha
  aleatória, invalidando integralmente o valor exposto antes da entrega.

Permanecem pendentes o primeiro acesso de Ismael, a troca da senha temporária,
o cadastro de MFA no dispositivo dele e a prova independente de recuperação.

## Branding do cliente em 01/09/2026

- customização suportada pelo `config.json`, sem fork do cliente Psono;
- assinatura `ness.` branca na entrada e na barra superior escura, com
  BlueDot `#00ade8`, reutilizando somente os PNGs aprovados do repositório;
- título normalizado para `ness. cofre`;
- tema com grid de 8 px, sombra suave, easing e
  `prefers-reduced-motion`;
- favicon original preservado até existir ativo oficial aprovado;
- backup pré-mudança `20260901T114659-0300` aprovado;
- backup pós-mudança `20260901T115242-0300` aprovado;
- rollback root-only preservado em
  `/opt/ness-os-psono/rollback/branding-pre-20260901T1147-0300`;
- PostgreSQL não reiniciado; somente `ness-psono` foi recriado e retornou
  saudável;
- JSON, Compose, mounts, configuração pública e CSS público aprovados.

A inspeção visual final em sessão limpa permanece pendente; configuração e
saúde operacional, isoladamente, não encerram o gate visual.

### Correção de contraste e persistência da rede

- a primeira inspeção visual reprovou a assinatura preta sobre o cartão escuro;
- `logo.png` foi substituído pelo ativo branco aprovado, preservando o BlueDot;
- o estado desabilitado do botão recebeu BlueDot com transparência, em vez do
  verde padrão do cliente;
- backup pré-correção `20260901T124437-0300` aprovado;
- backup pós-correção `20260901T125243-0300` aprovado;
- rollback root-only preservado em
  `/opt/ness-os-psono/rollback/branding-contrast-pre-20260901T1245`;
- a recriação removeu uma conexão manual com `app_ninf-net`, causando HTTP 502;
  a conexão foi restaurada e o acesso externo retornou a HTTP 200;
- a rede compartilhada passou a ser declarada como externa no Compose por
  `PSONO_SHARED_EDGE_NETWORK`, evitando a perda em futuras recriações.

### Título do navegador

- cliente e painel administrativo passaram a entregar `<title>vault ness.</title>`;
- a alteração usa mounts somente leitura sobre os HTMLs de entrada da imagem
  fixada, sem modificar os bundles do Psono;
- backup pré-mudança `20260901T130046-0300` aprovado;
- backup pós-mudança `20260901T130224-0300` aprovado;
- rollback root-only preservado em
  `/opt/ness-os-psono/rollback/browser-title-pre-20260901T1301`;
- cliente e portal validados externamente, healthcheck HTTP 200, rede do proxy
  presente e banco PostgreSQL sem reinício.

### Estabilização do branding e retirada do service worker

- causa confirmada: o service worker original precacheava `index.html`,
  `config.json` e `custom.css`, entregando versões visuais divergentes;
- o worker foi substituído por uma versão de retirada que apaga somente Cache
  Storage e seu próprio registro, sem tocar em cookies, senha, sessão,
  `localStorage`, `sessionStorage` ou IndexedDB;
- o carregador não registra novos workers;
- HTML, configuração, CSS e scripts de migração passaram a receber uma única
  política `Cache-Control: private, max-age=0, no-cache, no-store,
  must-revalidate`;
- `Clear-Site-Data: "cache"` foi aplicado temporariamente a `/server/info/` e
  `/server/user/status/` para retirar a cópia HTTP antiga sem apagar storage;
- backup pré-mudança `20260901T133628-0300` aprovado;
- backup pós-mudança `20260901T134131-0300` aprovado;
- rollback root-only preservado em
  `/opt/ness-os-psono/rollback/brand-cache-pre-20260901T1337`;
- título, logo aprovado, BlueDot, 20 healthchecks externos, rede do proxy e
  ausência de reinícios validados; PostgreSQL permaneceu ativo.

O cabeçalho temporário `Clear-Site-Data` deve ser removido depois da confirmação
visual do cliente ativo, preservando a retirada do service worker e as regras
`no-store` apenas para os artefatos mutáveis de identidade/configuração.

### Idioma inicial pt-BR em 02/09/2026

- o cliente e o portal suportam nativamente o locale `pt-BR`, mas a versão
  implantada não oferece uma chave de idioma padrão no `config.json`;
- `language-default.js` define `i18nextLng=pt-BR` somente quando ainda não há
  preferência no navegador, preservando o idioma escolhido pelo usuário e o
  idioma restaurado pelo Psono depois do login;
- os documentos de entrada declaram `lang="pt-BR"` e carregam o bootstrap
  antes dos bundles do cliente e do portal;
- o novo script e as entradas HTML/configuração do portal recebem a mesma
  política `Cache-Control` sem armazenamento usada pelos demais artefatos de
  branding;
- rollback root-only preservado em
  `/opt/ness-os-psono/rollback/ptbr-default-pre-20260902T150815-0300`;
- somente `ness-psono` foi recriado; PostgreSQL permaneceu saudável e com
  `StartedAt=2026-08-31T19:46:49.980462863Z`;
- cliente, portal, script, mounts e 20 requisições externas foram aprovados
  com HTTP 200; mediana de `/server/info/` em 673,1 ms e p95 em 1166,6 ms.

O cabeçalho temporário `Clear-Site-Data: "cache"` permaneceu ativo nessa etapa.
A confirmação visual e sua retirada controlada estão registradas na continuação
da onda F2 abaixo.

## Início da onda F2 — 02/09/2026 17:09–17:12 BRT

A baseline foi revalidada diretamente no host, sem leitura de credenciais ou
conteúdo do cofre:

- `ness-psono` e `ness-psono-db`: saudáveis; HTTPS: aprovado;
- backup de 02/09, 01:33–01:33 BRT: `Result=success`, código `0`; timer ativo
  para 03/09 às 01:39 BRT;
- ambientes Psono e Restic: `root:root 0600`;
- Ismael: conta ativa, superuser, primeiro acesso e troca de senha concluídos,
  MFA ativo;
- Ricardo: conta ativa, superuser e primeiro acesso concluído, mas MFA ainda
  inativo;
- nenhum emergency code criado; SMTP e recuperação de senha continuam
  desabilitados.

Foi criado `scripts/f2-readiness-report.sh`, um inventário somente leitura que
expõe apenas estados booleanos e contagens. Ele não consulta nem imprime senhas,
chaves, seeds MFA, recovery codes, emergency data ou conteúdo do cofre.

O renderizador também passou a suportar `PSONO_MULTIFACTOR_ENABLED`, inicialmente
`false`, com fatores limitados a TOTP e WebAuthn. A imposição global somente será
ativada depois da matrícula e prova de recuperação de ambos os custodians, para
evitar lockout administrativo.

Próxima sessão assistida obrigatória com os custodians:

1. Ricardo ativa MFA no próprio dispositivo e guarda os recovery codes fora da
   VPS e do repositório;
2. cada custodian comprova novo login com MFA e recuperação independente;
3. criar e testar emergency access com tempo de espera e notificação;
4. disponibilizar a chave Resend no arquivo runtime root-only, habilitar SMTP e
   testar ativação/recuperação sem registrar tokens;
5. repetir o relatório e manter o cofre bloqueado para credenciais reais até
   todos os cenários da PoC passarem.

### Continuação sem MFA — 02/09/2026

Por decisão do owner, a matrícula MFA restante foi adiada sem liberar o gate.
A trilha que independe dela foi expandida:

- chave Resend: ausente; SMTP permanece deliberadamente desabilitado;
- SOPS, age, chaves age e `.sops.yaml`: ausentes na baseline;
- criado instalador fail-closed para SOPS `3.13.3` e age `1.3.2`, com versões e
  SHA-256 fixados e recusa de sobrescrita de ferramentas divergentes;
- instalador aplicado na VPS AIOps e repetido com resultado
  `ALREADY_CURRENT`; versões efetivas: SOPS `3.13.3` e age/age-keygen `1.3.2`;
- confirmada a ausência de chaves privadas age em caminhos root/system e de
  política SOPS no stack Psono;
- a instalação das ferramentas não autoriza gerar chaves privadas em nome dos
  custodians, criar `.sops.yaml` com placeholders, migrar segredos ou revogar o
  caminho root-only atual.

A frente Authentik recebeu preparação adicional sem mudança de identidade: o
relatório read-only agora inventaria contagens de authenticators por tipo e
sessões autenticadas, além de grupos, aplicações e providers. A cópia foi
implantada em `/usr/local/sbin/ness-authentik-readiness-report`, sem dependência
de `jq`, e recusou execução sem credenciais. A coleta autenticada continua
pendente de um token read-only entregue por canal seguro, sem criação automática
de token.

### Validação visual e estabilização do cache — 02/09/2026 17:41–17:49 BRT

Uma sessão Chrome headless nova, sem perfil, cookies ou credenciais, comprovou:

- `<html lang="pt-BR">`, preferência inicial `i18nextLng=pt-BR` e interface em
  português;
- `<title>vault ness.</title>`;
- assinatura `ness.` branca com BlueDot no cartão escuro;
- cliente React montado sem erros de console, com os artefatos de identidade e
  configuração retornando HTTP 200.

A medição separou o custo do servidor do custo do cliente. Na própria VPS, a
página respondeu em 59 ms e `/server/info/` em 35 ms. Em uma sessão limpa em
São Paulo, o cliente levou de 3,5 a 4,1 s para ficar utilizável; o bundle de
4,13 MB (1,17 MB comprimido) consumiu cerca de 2,47 s desse caminho.

Como a retirada do service worker antigo já foi visualmente confirmada, o
cabeçalho temporário `Clear-Site-Data: "cache"` foi removido somente dos
endpoints `/server/info/` e `/server/user/status/`. As regras `no-store` dos
artefatos mutáveis e o worker auto-removível foram preservados. O Caddyfile foi
validado antes e depois, seguido de reload gracioso e healthchecks HTTP 200.

Depois da mudança, o recarregamento no mesmo navegador caiu para 0,38 s e o
bundle foi servido integralmente do cache (`transferSize=0`), contra 4,09 s no
primeiro acesso limpo. O cabeçalho também foi confirmado ausente externamente.
Rollback e evidências estão em
`/opt/ness-os-psono/rollback/clear-site-data-remove-corrected-20260902T175255-0300`.
Uma primeira tentativa não alterou o arquivo persistente por uma expressão de
remoção incorreta; a validação foi endurecida com comparações e falhas
explícitas antes da reaplicação. O estado final foi comprovado tanto no arquivo
montado quanto na resposta HTTP ativa.

O texto legado “Baixar Psono” e glifos auxiliares que não renderizaram no
Chrome headless foram classificados como polimento visual. Eles não impedem
login e serão tratados na etapa final, sem ampliar agora o fork visual do
cliente.

### Transporte SMTP observado — 02/09/2026 17:58–18:07 BRT

Uma mudança separada, com rollback próprio em
`/opt/ness-os-psono/rollback/smtp-resend-pre-20260902T175843-0300`, ativou o
SMTP Resend e `ALLOW_LOST_PASSWORD`. A revalidação confirmou a credencial
runtime presente sem imprimir seu valor, arquivo `root:root 0600`, host
`smtp.resend.com`, porta 587 e STARTTLS.

O relatório F2 passou a distinguir configuração de credencial efetivamente
presente. Uma sessão SMTP autenticou e encerrou sem transmitir mensagem:
`smtp_auth_without_send=PASS`, `smtp_message_sent=no`. Isso prova DNS, rede,
TLS e autenticação; não prova entrega, link de recuperação ou proteção contra
reuso. Esses cenários permanecem pendentes de destinatário controlado.

O gate do cofre continua fechado para segredos reais: Ismael possui MFA, mas
ambos os custodians continuam sem recovery codes, Ricardo ainda não possui MFA,
não há emergency code e a imposição global de multifator permanece desligada.

### SMTP Resend operacional — 02/09/2026 17:58–18:00 BRT

A chave de envio restrita foi recebida fora do chat e do Git, instalada somente
em `/etc/ness-os/psono.env` (`root:root 0600`) e removida da área temporária de
transferência. Antes da mudança foi preservado rollback root-only em
`/opt/ness-os-psono/rollback/smtp-resend-pre-20260902T175843-0300`.

O renderizador testado foi promovido para fixar explicitamente MFA global como
desabilitado durante esta etapa. SMTP e recuperação de senha foram habilitados,
mantendo registro público fechado. A validação comprovou:

- autenticação Resend em `smtp.resend.com:587` com STARTTLS;
- envio real pelo backend Django/Psono para o destinatário de teste do Resend,
  com retorno `1`;
- `allow_lost_password=true` no cliente público e `/server/info/` HTTP 200;
- Psono e PostgreSQL saudáveis; somente `ness-psono` reiniciado, enquanto o
  banco preservou `StartedAt=2026-08-31T19:46:49.980462863Z`;
- relatório F2 aprovado, SMTP configurado, recovery habilitado e imposição MFA
  ainda desativada conforme decisão do owner.

A issue #44 permanece aberta até a jornada de recuperação de uma conta real,
a confirmação da notificação pelo custodian e a rotação da chave temporária
antes da promoção. Nenhum valor secreto foi registrado nas evidências.

## Issues de acompanhamento F2

- #43 — MFA, recovery codes e emergency access;
- #44 — SMTP Resend e recuperação;
- #45 — dois recipients age e promoção da política;
- #46 — migração de segredos por consumidor;
- #47 — acesso read-only e inventário Authentik;
- #48 — migração do Psono para VPS dedicada;
- #51 — jornadas Authentik/RBAC por aplicação.
