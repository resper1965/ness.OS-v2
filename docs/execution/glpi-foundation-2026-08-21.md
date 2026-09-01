# Fundação GLPI do ness.OS — 21/08/2026

## Resultado

A fundação foi iniciada sobre o GLPI Community 11.0.8 existente. A imagem está fixada pelo digest em execução, as credenciais de banco foram rotacionadas e o caminho de conexão persistente do GLPI foi sincronizado. A verificação pós-mudança confirmou HTTP 200, 466 tabelas e cron sem novo erro de conexão.

O inventário somente leitura encontrou:

- 12 entidades, incluindo a raiz Ness e entidades de clientes;
- 29 categorias de atendimento já organizadas por acesso, aplicações, infraestrutura, segurança, mudança e hosting;
- 8 SLAs e 1 template de ticket;
- 6 artigos de conhecimento publicados como FAQ;
- zero projetos e zero tarefas de projeto;
- zero categorias de conhecimento, apesar dos artigos existentes.

## Decisão de implantação

O catálogo existente será preservado e refinado, não recriado. Projetos e runbooks começam pelos objetos descritos em [`../../config/glpi/ness-os-foundation-v1.yaml`](../../config/glpi/ness-os-foundation-v1.yaml). O arquivo é um manifesto de governança e não contém dados fictícios inseridos no GLPI.

A carga remota permanece condicionada ao teste positivo da API pelo caminho de máquina aprovado. A conta técnica e os tokens de menor privilégio já existem; escrita direta no banco GLPI continua proibida porque contorna regras de negócio, histórico, auditoria e validação de entidade.

## Acessos observados

As identidades `resper`, `iaraujo`, `rsalerno` e `agsilva` existem no Authentik. O mapeamento atual mantém Ricardo no grupo administrativo cotidiano; Rogério e Ismael em `gestao`, `noc` e `usuarios`; Agnaldo permanece nos mesmos grupos operacionais, sem promoção global durante a observação.

O GLPI contém duplicatas nominais oriundas de fontes de autenticação diferentes. Há registros ativos `Observer` paralelos aos registros históricos de técnico/admin. Nenhum registro foi fundido, excluído ou promovido por SQL. A reconciliação deve ocorrer pela interface/API suportada, preservando tickets, histórico e vínculo com a fonte de autenticação.

O Hub ainda contém somente a conta local genérica. Seu fluxo OIDC já implementa provisionamento just-in-time e mapeia grupos Authentik para papéis locais; assim, as contas nominais surgirão no primeiro login homologado. A conta local será mantida apenas como contingência até dois logins nominais e MFA serem comprovados.

## Próxima carga controlada

1. Migrar os segredos temporários da conta técnica GLPI para o Psono Community/SOPS-age e revogar os valores de implantação antes do go-live.
2. Após aprovação formal do manifesto, executar o importador `app/backend/app/integrations/glpi_runbook_categories.py`: ele opera em dry-run por padrão e cria somente as oito categorias vazias de runbook via API suportada `KnowbaseItemCategory` quando recebe `--apply` e encontra `governance_status: approved`. O import é idempotente, sequencial, para em duplicidade ambígua e deve retornar zero criações na segunda execução. Categorias são taxonomia não sensível; conteúdo de clientes continua proibido até os testes de entidade.
3. Importar os cinco projetos piloto como rascunho e atribuir owner/sponsor após validação da Governança.
4. Converter os seis artigos existentes em estrutura de runbook ou classificá-los explicitamente como orientação.
5. Homologar login nominal no Hub, GLPI e Authentik para Ricardo, Rogério e Ismael; manter Agnaldo sem privilégio global.
6. Executar testes negativos com duas entidades descartáveis antes de publicar qualquer conteúdo para cliente.

O manifesto foi aprovado por Ricardo Esper em 24/08/2026 (`status` e `governance_status: approved`). Isso libera o gate de Governança, mas não autoriza SQL direto nem uso de credencial improvisada. A escrita continua aguardando o teste positivo da API pelo caminho de máquina aprovado e a aprovação do dry-run remoto. Não executar `import_catalog.py`: ele usa SSH/root, apaga categorias e grava diretamente no banco. Também não reutilizar scripts/planos legados que façam SQL direto para esta carga.

O importador controlado está implementado somente no repositório, sem deploy ou escrita no GLPI. A verificação local de 22/08/2026 aprovou os cinco cenários focados (dry-run sem POST, idempotência, bloqueio de draft antes de HTTP, oito criações sequenciais quando aprovado e recusa de ambiguidade) e uma seleção integrada de 16 testes de GLPI/RBAC. O manifesto real está `approved`; o `--apply` continua bloqueado operacionalmente até o acesso à API deixar de ser interceptado pelo SSO e o dry-run remoto ser aprovado.

O preparo dos projetos também avançou sem escrita: `app/backend/app/integrations/glpi_project_manifest.py` valida localmente os cinco projetos e 13 work packages, rejeitando campos obrigatórios ausentes, códigos duplicados, referências de projeto pai inexistentes e ciclos. O relatório é explicitamente `action=dry-run-only`, não cria cliente GLPI e não acessa rede ou credenciais. Em 22/08/2026, os testes combinados desse validador e do importador de categorias passaram (`10 passed`). Ainda não existe importador de projetos autorizado; owner/sponsor e aprovação formal continuam sendo gates de Governança.

## Preparação da API pela interface — 24/08/2026

Com confirmação explícita de Ricardo Esper e sessão autenticada como `AKADMIN`, foram aplicadas as seguintes mudanças pela interface suportada:

- cliente legado `ness-os-integration` (ID 2) mantido ativo;
- filtro IPv4 limitado exclusivamente à VPS AIOps `144.91.115.242`;
- valor inválido `glpi` removido do campo IPv6;
- registro de conexões alterado de desabilitado para `Logs`;
- perfil `ness.OS Integration` (ID 12) reduzido a seis direitos funcionais: leitura/criação de chamados, leitura/adição de acompanhamentos públicos e leitura/criação de categorias da base de conhecimento;
- as demais permissões herdadas foram removidas; o GLPI preserva 27 transições invariantes `estado → mesmo estado` nas matrizes de ciclo, sem conceder transição para outro estado;
- usuário local técnico `svc_ness_os` (ID 94) criado, ativo, sem e-mail, com uma única autorização na entidade raiz Ness, perfil ID 12 e sem recursividade;
- `app_token` do cliente ID 2 e `user_token` do usuário ID 94 gerados sem exposição em logs ou documentação;
- credenciais de implantação armazenadas temporariamente em `secrets/runtime/glpi-integration.env`, ignorado pelo Git, diretório `0700` e arquivo `0600`; migração ao cofre e revogação integral são obrigatórias antes do go-live.

Durante a verificação local do arquivo, o shell expandiu indevidamente os primeiros valores no retorno da ferramenta. O incidente foi contido no mesmo ciclo: senha técnica, `app_token` e `user_token` foram todos regenerados pela interface; o arquivo foi sobrescrito com os novos valores e os artefatos intermediários removidos. Os valores mostrados anteriormente estão revogados e não devem ser reutilizados.

O teste sem escrita contra `https://n-ticket.ness.com.br/apirest.php/initSession` não alcançou a API: o proxy Authentik respondeu `302` para seu fluxo OIDC. Assim, os tokens existem, mas a integração ainda não está funcional e nenhuma categoria/projeto foi criado. A correção preferida é expor a API por rota privada entre AIOps e GLPI; uma exceção pública no proxy só pode ser aceita se limitada estritamente ao caminho da API e combinada com tokens, controle de origem efetivo, rate limit e logs. Depois da correção, testar da VPS AIOps: `initSession`, leituras mínimas, `killSession`, origem negativa, dry-run remoto e somente então `--apply`.

## Evidência reutilizável

- [`../../infra/scripts/glpi-access-state-report.sh`](../../infra/scripts/glpi-access-state-report.sh): identidades e perfis, somente leitura e sem segredos.
- [`../../infra/scripts/glpi-foundation-state-report.sh`](../../infra/scripts/glpi-foundation-state-report.sh): contagens e taxonomias da fundação, somente leitura.
- [`../../infra/scripts/glpi-pin-and-rotate.sh`](../../infra/scripts/glpi-pin-and-rotate.sh): fixação/rotação transacional, agora sincronizando também o arquivo persistente de conexão.
- [`../../infra/scripts/glpi-sync-persistent-db-password.sh`](../../infra/scripts/glpi-sync-persistent-db-password.sh): correção idempotente usada no incidente pós-rotação.
