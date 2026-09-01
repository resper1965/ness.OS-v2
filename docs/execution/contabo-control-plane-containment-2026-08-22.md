# Contenção do plano de controle Contabo — 22/08/2026

## Resultado

A implementação existente contrariava os ADRs aceitos: continha rotas de reinstalação, energia, snapshots, console e secrets sem dependência server-side de autorização. Na imagem ativa, o router estava dormente porque o pacote `cli` não fazia parte do runtime, mas a simples correção desse empacotamento reativaria toda a superfície insegura.

Foi aplicada a contenção mínima:

- criado o papel `platform_admin` no modelo, migração PostgreSQL e mapeamento do grupo Authentik;
- router Contabo protegido integralmente por `require_platform_admin`;
- removidas todas as rotas `POST`/`DELETE`, console/VNC e secrets;
- removida a consulta e a devolução de secrets no dashboard agregado;
- PWA reduzida a visão somente leitura, sem reinício, console, criação/gestão de firewall ou aba de chaves;
- nenhuma nova dependência ou abstração adicionada.

## Verificação

- testes backend: 39 aprovados; três avisos de depreciação preexistentes;
- teste específico Contabo: quatro aprovados;
- build Vite: aprovado;
- migração aditiva `platform_admin`: concluída;
- API: `healthy`; frontend: `running`; borda Hub: HTTP 200;
- rotas Contabo e mutações: HTTP 404 enquanto o cliente oficial não estiver empacotado;
- bundle publicado sem os textos/URLs de ações, console e chaves removidos;
- rollback root-only preservado em `/var/backups/ness-os/contabo-rbac-` e `/var/backups/ness-os/contabo-rbac-20260822T1242-0300`.

Na mesma revisão, `/api/dashboard/problems` foi encontrado sem autorização. A rota passou a reutilizar `require_noc`; a suíte integrada subiu para 41 testes aprovados. Em produção, a API permaneceu `healthy`, a chamada sem token retornou HTTP 401, a borda continuou HTTP 200 e o rollback ficou em `/var/backups/ness-os/dashboard-rbac-20260822T1254-0300`.

Os endpoints globais `/api/core/overview` e `/api/core/kpis` também passaram de qualquer autenticado para `require_noc`; `/api/core/modules` permaneceu disponível a qualquer usuário autenticado porque contém somente catálogo de navegação. A implantação incluiu as correções já testadas de indicadores executivos que retiram soma de fontes heterogêneas e score sem fórmula homologada. A suíte integrada chegou a 46 testes; em produção, os três endpoints retornaram HTTP 401 sem token, a API permaneceu `healthy`, a borda HTTP 200 e o rollback ficou em `/var/backups/ness-os/core-rbac-indicators-20260822T1301-0300`.

## Pendências deliberadas

1. Criar e homologar o grupo Authentik `platform_admin` somente para Ricardo Esper, Ismael Araujo e Rogério Salerno, com MFA validado.
2. Empacotar o cliente Contabo no backend apenas depois dos testes negativos `401/403` e manter exclusivamente os endpoints GET aprovados.
3. Criar usuário/API Contabo de menor privilégio e leitura; não reutilizar credencial administrativa.
4. Implementar auditoria interna antes de qualquer mutação futura. Mutações permanecem fora do MVP.

### Runtime corrigido

O cliente existente em `app/cli` foi incluído na imagem sem nova dependência, com import obrigatório durante o build. Após rebuild/recreate, a API permaneceu `healthy`, o Hub HTTP 200, `GET /api/contabo/compute` retornou 401 sem autenticação e secrets/mutações retornaram 404. O rollback do Dockerfile anterior está em `/var/backups/ness-os/contabo-runtime-20260822T1331-0300`. A pendência 2 acima fica concluída; a liberação funcional continua bloqueada pela conta read-only, grupo/MFA e testes 403/200 nominais.

## Incidente de confidencialidade durante a verificação

Um comando de diagnóstico expandiu variáveis sensíveis do Compose no retorno da ferramenta. Nenhum valor será reproduzido na documentação, mas as credenciais de Contabo, aplicação/JWT/OIDC, bancos, Authentik, GLPI, n8n, Gemini, VAPID e API Zabbix presentes naquele ambiente devem ser tratadas como expostas. A rotação deve ser transacional, por consumidor, com backup/rollback e teste após cada troca; não executar rotação em massa sem cofre e plano de recuperação.
