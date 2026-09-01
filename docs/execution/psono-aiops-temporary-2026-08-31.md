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

Pendência controlada: remover o cabeçalho temporário `Clear-Site-Data` depois
da confirmação visual do cliente ativo.
