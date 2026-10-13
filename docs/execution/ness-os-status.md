# ness.OS — indicador de entrega

Última verificação: **13/10/2026, 19:16 BRT**. Fonte: plano master,
`PROJECT_CONTEXT.md`, estágio operacional, ledger e GitHub. Este quadro é um
checkpoint, não telemetria em tempo real. Atualizar quando uma entrega, gate,
bloqueio ou prazo mudar; preservar a data da última verificação.

**Estado global: 🔴 produção completa ainda não liberada.** Nenhuma fase
inteira abaixo deve ser chamada de concluída por CI verde, serviço `running`,
preparação UAT ou documentação isolada.

| Frente do master | Estado | Evidência e próximo marco |
|---|---|---|
| F0 — release/continuidade | 🟡 Parcial | PR 65 integrado antes da reescrita; SHA antigo substituído. PRs 64/81 seguem draft; SHAs, diffs e checks anteriores requerem nova validação. Run `38433314272` falhou no push GHCR (`write_package`); nenhum digest novo ou deploy. Buildx Windows construiu API/frontend localmente, frontend `npm ci`/lint/build/auditoria 0 vulnerabilidades e quatro testes focados PASS. Ubuntu/WSL acessa Docker/Buildx; o publicador completo ainda não executou. Histórico de heads/tags foi sanitizado e escaneado; refs de PR/caches ainda dependem do GitHub Support (issue #82). Actions desativado, quatro checks da `main` preservados e merges bloqueados até substituição segura. Repositório PRIVATE `resper1965/ness.OS-v2`; privatização não desfaz possível exposição histórica. G0/G1 globais não declarados PASS. |
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
passou, mas ainda falta executar o publicador completo e tratar refs de PR.
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
capturaria seu resultado; uma nova prova completa está em execução com
keepalive e exit code observável. Ainda não há aceite final da restauração.
Após a rotação, o histórico das 34 branches e uma tag foi reescrito e
publicado no remoto privado com leases; a `main` exigiu exceção temporária de
administrador e sua proteção foi restaurada (PR, quatro checks, admin, sem
force-push). Um clone novo contendo apenas heads/tags reproduziu as 35
referências e passou no scan histórico com exceções pontuais revisadas para
falsos positivos. Os refs de PR e caches do GitHub ainda podem conter o
histórico antigo; solicitar limpeza ao GitHub Support. A restauração externa
completa pós-rotação ainda está em verificação; leitura de manifesto passou.
Nenhum valor secreto foi incluído neste indicador. PRs 64/81 seguem draft,
sem checks externos, revisão ou imagem publicada.

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

**Checks locais após a reescrita:** PR 81 foi rebaseado na `main` limpa e a
fixture sintética de token foi ajustada; 12 testes focados, scan Git e scan do
checkout passaram. O conjunto completo ainda falha em baseline preexistente:
Black requer formatação de 26 arquivos, Ruff aponta lint/formatação, Mypy
encontra seis erros em quatro arquivos e `flake8` não está instalado no builder.
Esses gates não foram dispensados; o PR permanece draft/bloqueado.

**Foco agora:** GLPI T03 e substituição segura do pipeline. PR 65 foi integrado;
próxima liberação depende da revisão técnica do PR 64, publicação segura de
imagem por digest e matriz negativa real da rota direta, rota
pública autenticada e entidade descendente; só então considerar ativar a
identidade mínima 106 e reconciliar ativos/tickets em ondas. Trabalho
independente GLPI continua. Zabbix não corta por extensão da janela apenas.

**Regra do indicador:** 🟢 = aceite comprovado; 🟡 = entrega parcial ou em
execução; 🔴 = gate obrigatório não satisfeito; ⚪ = sem aceite produtivo.
Nunca converter estados em porcentagem inventada.
