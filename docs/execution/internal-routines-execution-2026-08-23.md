# Execução das rotinas internas do ness.OS — 23/08/2026

## Escopo

Foram executadas todas as rotinas seguras identificadas que não dependem de compra de VPS, contratação de serviço externo ou criação de credencial inexistente. Não houve deploy produtivo, alteração direta em banco, concessão de privilégio, reinício de serviço crítico ou repetição de restore já aprovado.

## Resultado executivo

| Trilha | Resultado | Evidência |
|---|---|---|
| Backend | aprovado | Ruff lint e format aprovados; suíte completa passou |
| Frontend | aprovado com dívida não bloqueante | Oxlint sem erros, build Vite aprovado; avisos reduzidos de 33 para 9 |
| Tooling de infraestrutura | aprovado | sintaxe dos 29 scripts e testes estáticos Restic/verificador Zabbix passaram |
| Repositório | aprovado com quarentena | `git diff --check` passou; a triagem posterior moveu segredos/runtimes ignorados e o Gitleaks passou com zero achado |
| AIOps remoto | saudável | 14 contêineres ativos, componentes com healthcheck saudáveis, Compose válido, sem unit systemd falha observada |
| Segredos AIOps | consistente | consumidores usam a mesma senha de banco; defaults conhecidos ausentes; valores não foram exibidos |
| GLPI | baseline confirmada | 12 entidades, 29 categorias, 8 SLAs, 6 artigos, zero projetos/tarefas/categorias de conhecimento |
| GLPI dry-run | aprovado | 5 projetos e 13 work packages; 10 testes de manifesto/categorias passaram; nenhuma escrita |
| Zabbix KVM8 | quarentena aprovada | server inativo/mascarado, zero listener 10051, MariaDB ativo e somente local |
| Portal/API pública | proteção aprovada | endpoints privilegiados Contabo, dashboard e core retornam 401 anonimamente |
| Documentação | aprovada | 63 documentos verificados, zero link Markdown local quebrado; seis YAMLs válidos |

## Correções aplicadas

1. Corrigida a string não encerrada em `contabo_firewall.py`; a operação `block_ip` agora falha explicitamente porque a API descrita não suporta regra `drop` nesse cliente.
2. Corrigido timestamp UTC no endpoint de triagem e no Web Push.
3. Corrigido uso de símbolo inexistente `func` no Web Push.
4. Corrigidos imports, tratamento de exceção e lint do backend; 68 arquivos do pacote estão no formato esperado pelo Ruff.
5. Adicionado teste que impede montar o router mutável Contabo na superfície `/api/contabo`; somente GET/HEAD são aceitos.
6. Removidos imports/estados frontend sem uso e corrigidas dependências stale dos callbacks de dashboard/incidentes.
7. Alinhado o tipo frontend ao papel `platform_admin` e demais papéis já existentes no backend.

## Fotografias operacionais

### AIOps

- 14 contêineres ativos;
- API e workers com healthcheck saudável;
- 339 GiB livres, 11% do filesystem utilizado;
- aproximadamente 19 GiB de memória disponível e swap sem uso;
- timer de backup AIOps habilitado;
- Hub e saúde Authentik HTTP 200; n8n e n-ticket redirecionam ao Authentik;
- Compose remoto: `PASS`.

### GLPI

- as quatro identidades nominais existem, mas cada uma possui duplicata `Observer`;
- Ricardo possui um registro histórico inativo Super-Admin e um registro ativo Observer;
- Ismael, Rogério e Agnaldo também têm registros paralelos;
- nenhuma fusão, exclusão ou promoção foi executada;
- manifesto aprovado por Ricardo Esper em 24/08/2026; escrita ainda bloqueada até existir conta API nominal e cofre para o token.

### Zabbix staging

- `zabbix-server`: `inactive` e `masked`;
- listener TCP/10051: zero;
- MariaDB: ativo e sem listener não local;
- evidência pós-restore preservada;
- restore/transfer não foram repetidos.

## Bloqueios residuais que não são compra de VPS

| Bloqueio | Motivo para não executar automaticamente |
|---|---|
| Aprovar/importar manifesto GLPI | requer aprovação formal e conta API nominal de menor privilégio |
| Reconciliar duplicidades GLPI | mudança de identidade/histórico; deve usar interface/API suportada e rollback |
| Criar/atribuir `platform_admin` | requer token/API suportada, MFA dos três administradores e teste negativo antes da concessão |
| Homologar SSO humano | depende de interação dos usuários de teste e matrícula MFA |
| Deploy AIOps | workflow permanece deliberadamente desabilitado pelo Gate 0; não foi contornado |
| Executar Zabbix em staging | instrução do Gate mantém o server mascarado até critérios GO/NO-GO |
| Sanear achados Gitleaks | concluído sem exclusão; arquivos ignorados foram separados em quarentena externa recuperável |
| Eliminar os 9 avisos React restantes | exigem refatoração do ciclo de efeitos/sessão; build e lint já passam, tratar no WP08/hardening |

## Bloqueios externos

- Contabo Object Storage e os cinco insumos Restic/S3;
- VPS, domínio e SMTP do Psono Community;
- owner/tenant/endpoints do piloto e BOM aprovada antes do Wazuh.

## Critério de continuação

A próxima execução segura pode avançar assim que houver: aprovação do manifesto GLPI, matrícula MFA, credencial nominal das APIs e/ou Object Storage. Até lá, repetir restores, habilitar Zabbix, realizar deploy manual ou limpar arquivos não rastreados não acrescenta evidência e aumenta risco.
