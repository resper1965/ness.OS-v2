# ness.OS — indicador de entrega

Última verificação: **13/10/2026, 21:14 BRT**. Fonte: plano master,
`PROJECT_CONTEXT.md`, estágio operacional, ledger e GitHub. Este quadro é um
checkpoint, não telemetria em tempo real. Atualizar quando uma entrega, gate,
bloqueio ou prazo mudar; preservar a data da última verificação.

**Estado global: 🔴 produção completa ainda não liberada.** Nenhuma fase
inteira abaixo deve ser chamada de concluída por CI verde, serviço `running`,
preparação UAT ou documentação isolada.

| Frente do master | Estado | Evidência e próximo marco |
|---|---|---|
| F0 — release/continuidade | 🟡 Parcial | PR 65 integrado antes da reescrita; SHA antigo substituído. PRs 64/81 seguem draft; SHAs, diffs e checks anteriores requerem nova validação. O publicador local no commit `92eced4` passou nos checks completos, publicou API/frontend no GHCR privado e ambos foram puxados por digest; nenhum deploy. O run Actions antigo `38433314272` falhara com `write_package`, agora sem relevância para o builder local. Histórico de heads/tags sanitizado e escaneado; refs de PR/caches ainda dependem do GitHub Support (issue #82). Actions desativado; App privada `ness-os-local-ci` criada/instalada somente em `ness.OS-v2`, chave nova local `root:root 0600` e token temporário usado apenas para leitura no ensaio. Quatro checks da `main` continuam vinculados ao app Actions (`app_id=15368`): merges bloqueados até emissor externo confiável e troca controlada da origem. Repositório PRIVATE `resper1965/ness.OS-v2`. G0/G1 globais não declarados PASS. |
| F1 — Authentik/tenant/Psono | 🟡 Parcial | Marca e login público Authentik verificados; MFA nominal, recuperação, jornadas autenticadas/tenant e Psono dedicado ainda sem aceite. G2 aberto. |
| F2 — Zabbix definitivo | 🟡 UAT preparada | Destino restaurado e isolado; origem segue única coletora. Referência: 262 hosts reais + 63 protótipos; 2,086% unsupported na última amostra. SSO nominal, qualidade da frota, gates, freeze e GO faltam antes do corte. Janela até 15/10 11:47:35 BRT; token anterior expirado. |
| F3 — GLPI | 🟡 Em execução | Volume persistente e borda pública corrigidos; busca idempotente, paginação, alias privado fixo e importação isolada do gateway endurecidos na branch, sem deploy. API real confirmou o contrato de paginação; imagem local sem rede importou o gateway sem inicializar VAPID. Conta 106 desativada; gateway candidato, três ativos e replay aguardam T03. Ações automáticas: 18 internas atrasadas, sem conversão; `graph` elimina arquivos antigos e não serve como canário sem efeito. Os sete agentes têm último contato em julho; piloto autenticado/isolamento registrados na issue #79, não executados. Deduplicação restante e tema ness. aguardam decisão/teste nominal. |
| F4 — Hub/PWA | 🟡 Parcial | Runtime anterior promovido e rollback ensaiado; mudanças recentes estão só na branch. G3 e jornada produtiva por tenant/perfil não aceitos. |
| F5 — operação integrada | 🔴 Pendente | Sem prova produtiva completa evento → incidente → ticket, replay/timeout, papéis e todas as entidades. G4 não aprovado. |
| F6 — AIOps/automação | 🟡 Parcial | Componentes existentes, mas RCA/Node-RED e jornadas assistidas ampliadas sem aceite produtivo global. |
| F7 — Wazuh/Workspace | ⚪ Sem aceite | Capacidade/custo, isolamento, ingestão e rollout por faixa ainda pendentes. G5 não aprovado. |
| F8 — marca/sustentação | 🟡 Parcial | Camadas ness. aplicadas em algumas superfícies; render nominal GLPI, marca completa, runbooks testados e observação D+1/D+3/D+7 após cortes ainda pendentes. |

**Atualização F0:** Ubuntu/WSL acessa Docker Desktop 29.8.0 e Buildx 0.37.
O impedimento de integração foi removido; o scan das referências publicadas
e o publicador completo passaram, mas ainda faltam refs de PR e status externo.
Varredura local redigida na
branch atual encontrou 11 achados históricos em sete caminhos; os três
campos sensíveis do inventário já usam referência de ambiente no HEAD, mas
o histórico continua exigindo classificação e remediação. A tentativa
anterior de validar os candidatos antigos leu essas referências, não os
valores históricos; seu resultado foi invalidado. Uma consulta de diagnóstico
expôs a credencial S3 e a senha Restic ativas na saída da ferramenta.
A nova chave S3 nominal foi testada com leitura do bucket e instalada no
EnvironmentFile root-only; leitura do repositório Restic passou. O segredo S3
histórico pertence ao mesmo Access ID regenerado. A senha MariaDB histórica
ainda autenticava `root@localhost`; foi rotacionada pelo mecanismo nativo,
com nova senha aceita, antiga recusada, leitura da conta `zabbix` e serviços
ativos. A senha Restic foi rotacionada com o lock livre: a nova abriu os
snapshots, a antiga foi recusada e o manifesto externo coincidiu byte a byte
com o local. O primeiro restore completo terminou após perda da conexão que
capturaria seu resultado. A nova prova externa isolada, com keepalive e exit
code observável, terminou com código 0: `isolated_restore=PASS` e
`external_restore=PASS` para o mesmo conjunto de backup. Isto comprova a
recuperação desse conjunto, não a prontidão do release ou um gate global.
Após a rotação, o histórico das 34 branches e uma tag foi reescrito e
publicado no remoto privado com leases; a `main` exigiu exceção temporária de
administrador e sua proteção foi restaurada (PR, quatro checks, admin, sem
force-push). Um clone novo contendo apenas heads/tags reproduziu as 35
referências e passou no scan histórico com exceções pontuais revisadas para
falsos positivos. Os refs de PR e caches do GitHub ainda podem conter o
histórico antigo; solicitar limpeza ao GitHub Support. A restauração externa
completa pós-rotação terminou com código 0 e PASS isolado/externo para o
conjunto `20261012T220019-0300`.
Nenhum valor secreto foi incluído neste indicador. PRs 64/81 seguem draft,
sem checks externos, revisão ou deploy; as imagens candidatas do PR81 foram
publicadas e lidas por digest, mas não promovidas.

**Atualização F3:** gateway GLPI candidato agora encerra o cliente mesmo
quando recusa URL não privada; teste RED→GREEN e backend 486 PASS/1 SKIP.
Importação isolada também evita inicialização incidental de VAPID; teste
RED→GREEN, backend 487 PASS/1 SKIP e smoke da imagem local sem rede PASS.
O runtime passou a exigir o alias privado exato do Compose antes de ler
secrets; teste RED→GREEN e backend 488 PASS/1 SKIP.
Smoke local do processo Uvicorn sem rede e com tokens sintéticos: `/live` 200,
leitura sem bearer 401; contêiner descartável removido.
Ensaio Compose detectou falha de leitura de secrets root:root 0600 pelo UID
`nessops`; entrada opt-in corrigida para carregá-los como root e descartar
privilégios antes de servir. Preflight exige root/dono correto; ensaio local
com UID/GID 999, capacidades efetivas zero e healthcheck saudável; backend+infra
524 PASS/1 SKIP. Sem imagem publicada, deploy ou credencial real.
Ainda sem deploy, isolamento direto real ou reativação da conta 106.
T04: a revisão do timeout após POST confirmou que busca negativa imediata não
comprova ausência remota. A branch candidata passou a reservar uma única
tentativa por entidade/fingerprint no banco **antes** do POST; teste RED→GREEN,
525 testes backend+infra PASS/1 SKIP e esquema ensaiado em PostgreSQL descartável
(primeiro claim 1, repetido 0, outra entidade 1). Sem migração/deploy produtivo;
ensaio da função real com PostgreSQL descartável confirmou um único POST após
duas buscas vazias e reconciliação posterior. Replay continua bloqueado até
release, migração produtiva e reconciliação. Upgrade idempotente do esquema
foi adicionado ao caminho `app.migrate` (teste RED→GREEN), ainda sem execução
no banco produtivo.

**Checks locais após a reescrita:** PR 81 foi rebaseado na `main` limpa. A
fixture sintética de token e o baseline de formatação/lint/tipagem foram
corrigidos em commits separados. No builder, o conjunto completo passou:
Black, Flake8, Ruff, Mypy, 24 testes backend, `npm ci`, lint e build frontend;
auditoria npm encontrou zero vulnerabilidades. Quatro testes do publicador e
scans Git/checkout também passaram. O publicador integrou o fluxo e gerou
digests de API/frontend; pull por digest passou e ambos os pacotes GHCR seguem
privados. O PR permanece draft/bloqueado: falta status externo confiável,
revisão e prova de pull com a identidade de produção antes de qualquer deploy.

**App local de CI (19:59 BRT):** GitHub App privada `ness-os-local-ci`
(`App ID 5307771`, instalação `171160625`) criada com webhook desligado,
`Checks: write`, `Contents: read` e somente o repositório privado
`resper1965/ness.OS-v2`. Chave nova fora do Git em arquivo local
`root:root 0600` (cópia anterior legível pelo executor removida após
comparação e validação); o usuário de testes não consegue lê-la;
fingerprint e emissão de token de instalação de curta duração verificados,
sem registrar o token. Nenhum check foi emitido e a proteção da `main` não
mudou. A primeira chave, baixada na pasta OneDrive (informada pelo usuário
como não sincronizada), teve sua cópia local removida; a UI do GitHub ainda
mostra essa chave ativa e desabilita a exclusão mesmo com duas chaves. Tratá-la
como pendência de revogação, sem usar a chave anterior.

**Sandbox local (20:11 BRT):** checkout limpo da branch PR #81 teve
backend `24/24` e frontend lint/build PASS em contêineres sem rede, sem
Docker socket e sem chave; hashes do lock/requirements coincidiram com as
imagens de dependências. Frontend recebeu arquivo Git do SHA; backend recebeu
montagem somente leitura. É prova de viabilidade, não runner integrado nem
check emitido. PR #81 continua draft e a proteção da `main` inalterada.

**Publicador local (20:36 BRT):** PR #81 commit `071eb97` agora exige pull
das duas imagens por digest antes de gravar o manifesto de release. Teste de
falha de pull RED→GREEN; cinco testes do publicador e Flake8 focado PASS.
Nenhuma nova imagem foi construída/publicada nesse ajuste. O script ainda
executa checks no host; não rodá-lo diretamente de PR não revisado nem junto
da chave da App. Runner isolado e emissor de checks continuam pendentes.

**Launcher backend (20:46 BRT):** PR #81 commit `a219bde` contém launcher
candidato para checkout limpo/SHA exato e imagem local por ID imutável. Dois
testes de contrato passaram; execução real no Docker sem rede/socket/chave,
fonte somente leitura e UID sem privilégio concluiu `24/24` testes backend.
Ainda é código na branch de PR, não instalado como runner confiável fora do
checkout; frontend, lint/tipos, secret scan e emissor permanecem pendentes.
Nenhum check externo, mudança de proteção ou deploy decorre desse ensaio.

**Sandbox conjunto (20:56 BRT):** PR #81 commit `5a184a9` ampliou o launcher
candidato com frontend opcional: arquivo Git do SHA alimenta contêiner sem
rede/montagem do host; backend segue em montagem somente leitura. No commit
limpo `1b1abde`, backend `24/24`, frontend lint zero avisos e build PASS.
Três testes do launcher e oito testes de infra PASS. Ainda faltam Black,
Flake8, Ruff, Mypy e Gitleaks em execução isolada, cópia confiável do launcher
fora do PR, emissor da App e falhas negativas ponta a ponta. Sem check externo,
mudança de proteção, merge ou deploy.

**Qualidade Python isolada (21:12 BRT):** PR #81 acrescentou imagem de
ferramentas com base por digest e versões fixas. O primeiro ensaio real
falhou porque Ruff tentou gravar cache no checkout somente leitura; o cache
foi redirecionado para tmpfs após teste RED→GREEN. No commit `f07ca2d`,
backend `24/24`, Black, Flake8, Ruff check/format e Mypy passaram no
Docker sem rede, socket ou chave; quatro testes do launcher passaram.
Gitleaks isolado, instalação de cópia confiável do launcher fora do PR,
emissor externo e falhas negativas ponta a ponta ainda faltam. Sem check
externo, alteração da proteção, merge, deploy ou ativação GLPI 106.

**Scan isolado (21:14 BRT):** ensaio do Gitleaks em contêiner sem rede,
socket ou chave revelou que um erro Git de ownership podia ir para stderr
com exit code zero. O launcher agora configura `safe.directory` apenas para
o checkout montado e falha fechado em stderr ou código não zero. No commit
`e1501ae`, scan real e backend `24/24` PASS; seis testes do launcher PASS.
Ainda falta retirar a lista de exceções do controle do PR, instalar runner
revisado fora do checkout e integrar emissor/negações. Nenhum check externo,
proteção alterada, merge ou deploy.

**Foco agora:** GLPI T03 e substituição segura do pipeline. PR 65 foi integrado;
próxima liberação depende da revisão técnica do PR 64, publicação segura de
imagem por digest e matriz negativa real da rota direta, rota
pública autenticada e entidade descendente; só então considerar ativar a
identidade mínima 106 e reconciliar ativos/tickets em ondas. Trabalho
independente GLPI continua. Zabbix não corta por extensão da janela apenas.

**Regra do indicador:** 🟢 = aceite comprovado; 🟡 = entrega parcial ou em
execução; 🔴 = gate obrigatório não satisfeito; ⚪ = sem aceite produtivo.
Nunca converter estados em porcentagem inventada.
