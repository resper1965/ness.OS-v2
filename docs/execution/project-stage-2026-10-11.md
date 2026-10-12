# ness.OS — estágio operacional em 2026-10-11

## Atualização de execução em 2026-10-12

### Recuperação Hub/AIOps — G1 parcial do programa

O conjunto atual `20261012T085531-0300` foi enviado ao Object Storage Contabo
como snapshot `43192e11`, passou `restic check` e foi restaurado de volta em
isolamento com `remote=1` em 196 segundos. A prova corrigiu a unidade semanal,
que antes verificava somente o conjunto local; agora ela exige o snapshot
externo. Evidência: [`hub-aiops-recovery-2026-10-12.md`](evidence/hub-aiops-recovery-2026-10-12.md).

Isso aprova apenas G1-Hub/AIOps. O G1 global segue parcial até renovar as
provas de Zabbix, GLPI, Authentik e Psono.

### Identidade — início de G2 em somente leitura

O Authentik está saudável, mas a fotografia atual impede a aprovação de G2:
o grupo `platform_admin` recebeu os três membros nominais Ismael, Rogerio e
Ricardo e o backend comprovou o mapeamento da claim. Ainda não existem
dispositivos TOTP, WebAuthn ou códigos estáticos de recuperação. A evidência
não expõe segredos e está em
[`authentik-g2-readonly-inventory-2026-10-12.md`](evidence/authentik-g2-readonly-inventory-2026-10-12.md).
O próximo requisito é a inscrição MFA pelos próprios custodians e o teste de
revogação.

### Cofre — recuperação atual

O Psono passou em restauração externa isolada do conjunto
`20261012T013812-0300`, com aplicação HTTP 200, assinatura válida, chave
pública confirmada e RTO de 36 segundos. A evidência está em
[`psono-recovery-2026-10-12.md`](evidence/psono-recovery-2026-10-12.md).
Ele continua uma PoC na VPS AIOps: promoção dedicada e dupla custódia com MFA
seguem obrigatórias para G2.

A leitura F2 atual confirmou os dois custodians ativos, superusuários e com
primeiro acesso concluído; Ismael já possui MFA, Ricardo ainda não. Não há
códigos de recuperação ou emergência e MFA ainda não é imposto. A mesma leitura
detectou recuperação por senha e SMTP ativos, divergindo da documentação
histórica. O comportamento foi registrado como pendência, sem mudança
automática que pudesse comprometer a recuperação.

O scan do commit atual (`HEAD^..HEAD`) não encontrou segredos. A varredura da
árvore local encontrou apenas arquivos operacionais ignorados (`0600`) e cópias
no worktree auxiliar; eles não estão rastreados. Já o scan de histórico ainda
encontra três ocorrências em commits antigos, que não provam uma credencial
ativa, mas exigem rotação e decisão de saneamento antes de declarar a linha do
tempo do Git totalmente livre de segredos.

O Hub/AIOps foi promovido em janela controlada para o commit
`144317fd5262ecf242b118774573a62df8e88d78`, com imagens privadas GHCR por
digest, backup prévio `20261012T085531-0300`, migração aditiva, canário,
rollback controlado e re-promoção aprovados. A API e os dois workers estão
`healthy`; o frontend responde HTTP 200. Consulte a evidência completa em
[`hub-immutable-release-2026-10-12.md`](evidence/hub-immutable-release-2026-10-12.md).

Isto não aprova o programa inteiro: G0 continua parcial até CI completo em
runner limpo e integração da workflow de publicação protegida por revisão.

**Horários da coleta:** 2026-10-11 23:38–23:42 BRT (2026-10-12 02:38–02:42 UTC)  
**Branch/commit de referência:** `feat/incidents-rbac-local` / `51bb22c`  
**Owner operacional:** plataforma ness.  
**Escopo desta coleta:** somente leitura. Não houve alteração em DNS, coleta,
notificações, identidade, dados ou credenciais.

## Fotografia observada agora

| Componente | Observação atual | Resultado |
|---|---|---|
| Repositório | Branch alinhada a `origin/feat/incidents-rbac-local`; sem alterações locais no início da coleta | `observado` |
| Manifesto local G0 | Após excluir worktrees auxiliares da descoberta, identificou 19 imagens da release principal e oito referências sem digest | `reprovado` |
| Zabbix origem `zabbix-srv01` | Serviço `zabbix-server` ativo; timer local de backup ativo; conjunto `20261011T220025-0300` concluído às 22:31 BRT | `observado` |
| Backup local Zabbix | Diretório, `COMPLETED` e `SHA256SUMS` presentes; ainda falta checksum integral desta rodada e restore isolado renovado | `parcial` |
| Object Storage Zabbix | Último serviço terminou com sucesso às 05:33 BRT; `restic check` sem erros e snapshot do conjunto `20261010T220026-0300` listado no log | `parcial` |
| Destino Zabbix `zbx-prd-01` | `zabbix-server` permanece inativo; timer local está `failed` desde 02/09 porque tenta iniciar serviço deliberadamente mascarado | `bloqueio de desenho` |
| Backup local do destino | Último conjunto local é `20260901T220005-0300`; não é evidência atual de recuperação | `desatualizado` |
| AIOps `144.91.115.242` | Timers de backup e Object Storage ativos; backup local terminou às 23:06 BRT e cópia externa às 00:32 BRT, ambos com `Result=success` | `observado` |
| Runtime AIOps | 16 contêineres ativos; API, frontend e workers usam imagens locais `app-*`; demais imagens aparecem por tag no runtime. Hashes dos dois Compose ativos foram coletados sem conteúdo | `observado; G0 bloqueado` |
| Hub, GLPI, Authentik, Psono, Contabo API | Nenhuma evidência operacional renovada nesta coleta | `desconhecido` |

## Decisões e limites aplicados

1. O destino Zabbix não será "reparado" habilitando `zabbix-server`: o seu
   mascaramento é o controle de isolamento de Z-M2/Z-M3. A correção necessária
   é separar o timer de backup do destino isolado ou condicioná-lo ao estado do
   serviço, com ensaio e rollback antes de qualquer aplicação.
2. O sucesso do serviço de Object Storage prova a execução do job, não substitui
   restore isolado do snapshot mais recente. G1 permanece aberto.
3. Evidências anteriores permanecem históricas; não são usadas como aprovação
   de gates produtivos sem revalidação datada.
4. O corte Zabbix, DNS, proxies, agentes, ações, mídias e conectores continuam
   bloqueados. A origem é o rollback até o fim de Z-M5 e da observação.
5. A descoberta de Compose do manifesto ignora `.worktrees/`; isso elimina
   referências auxiliares fora da release sem esconder os oito bloqueios reais
   de imagem sem digest (`app`: API, frontend e dois workers; raiz: API,
   Caddy, Evolution API e PostgreSQL).
6. A leitura do runtime AIOps confirma o motivo do bloqueio: o deploy efetivo
   usa imagens locais `app-api`, `app-frontend`, `app-worker-alerts` e
   `app-worker-ml`, e imagens externas por tag. O próximo incremento G0 deve
   produzir imagens OCI por build, registrar seus digests e remover bind-mount
   de código do perfil de produção; não será resolvido alterando tags em um
   runtime já ativo.

## Validações locais desta execução

- Regressão do manifesto: `11 passed`.
- Testes estáticos de Object Storage/Restic e readiness AIOps: aprovados.
- Frontend: typecheck, lint e build aprovados; lint emitiu somente um aviso de
  Fast Refresh em `src/hooks/useAuth.tsx`.
- `git diff --check`: aprovado.
- Backend: a execução com o Python global parou no primeiro teste que importa
  `pywebpush`; a dependência está declarada em `requirements.txt`, mas não está
  instalada no runner atual. A repetição isolada também não pôde iniciar porque
  este host não possui `python3.12-venv`/`ensurepip`. Isto é falha de preparo do
  runner, registrada como bloqueio G0; não foi instalado pacote no host nem
  alterado código de aplicação.

Esses testes não aprovam G0: a árvore está deliberadamente modificada por esta
atualização e ainda há oito imagens sem digest. Nenhum runtime foi promovido.

## Registro único de gates

| Gate | Estado | Próxima prova objetiva |
|---|---|---|
| G0 — release reproduzível | `aberto` | Reconciliar runtime, imagens/digests, manifesto, CI limpo e ensaio de rollback |
| G1 — recuperação | `parcial` | Checksums e restores isolados atuais para Zabbix, Hub/AIOps, GLPI, Psono e Authentik; RTO medido |
| G2 — identidade/cofre | `aberto` | Inventário por aplicação, MFA/revogação/tenant, Psono dedicado e dupla custódia |
| Z-M1 — baseline | `aberto` | Baseline única origem/destino com fila, NVPS, itens, templates, ações e conectores |
| Z-M2/Z-M3 — destino isolado | `parcial` | Corrigir desenho do timer sem desmascarar servidor e renovar restore/baseline |
| Z-M4 — homologação | `aberto` | Piloto interno 5–10 ativos e depois Cavan — Matriz, sem canais externos |
| Z-M5 — corte | `bloqueado` | Depende de G0, G1, G2 e Z-M1–Z-M4, janela e GO formal |
| G3 — runtime Hub | `aberto` | Compose real, readiness fail-closed, RBAC HTTP/SSE e remoção de mocks |
| G4 — MVP interno | `bloqueado` | Evento sintético Zabbix → Hub → GLPI, replay, retry e recovery |
| G5 — Wazuh/Workspace | `planejado` | Pós-MVP, BOM aprovada e piloto mensurado |

## Risco aceito e revisão

A cópia externa inicial é exclusivamente Contabo Object Storage. Ela não atende
integralmente à regra 3-2-1; o risco é aceito somente de forma temporária e
deve ser reavaliado trimestralmente, junto com retenção, custo, capacidade e
estratégia de segunda cópia independente.

## Rollback conhecido

- **Zabbix:** manter origem, sem apagar banco restaurado no destino; retorno de
  DNS somente por mudança aprovada após Z-M5.
- **Release Hub:** promover apenas manifesto identificado e conservar artefato
  anterior compatível com migrations; rollback testado é pré-requisito G0.
- **Backups:** não remover snapshots atuais ou conjuntos `COMPLETED` durante
  novos ensaios de restore.

## Próxima execução segura

1. Criar o manifesto de release a partir do runtime efetivo e executar a suíte
   G0 em ambiente limpo.
2. Colher baseline somente leitura da origem e do destino Zabbix, inclusive
   banco, templates, filas e estado de integrações.
3. Projetar e testar localmente o ajuste do timer de backup do destino isolado;
   aplicar somente com ticket GLPI, janela e rollback.
4. Revalidar restore isolado atual de cada produtor de backup antes de declarar
   G1 aprovado.

