# Skills para conclusão do ness.OS

## Decisão recomendada

Criar uma skill interna `ness-os-completion` é mais segura e útil que instalar uma skill DevOps genérica. O projeto possui regras próprias — janelas de manutenção, Gate 0, contas nominais, evidências, hardening pós-implantação, sistemas canônicos, RBAC e proibição de registrar segredos — que uma skill pública não conhece.

A skill deve orquestrar, sem conter credenciais:

1. leitura da arquitetura oficial e das ADRs;
2. seleção do próximo gate incompleto;
3. checagem de janela e impacto no Zabbix;
4. backup, checksum, cópia externa e restore isolado;
5. implantação, hardening e polimento funcional;
6. validação de coleta, mapas, localização, SSO/MFA e RBAC;
7. atualização de evidências, as-built, runbooks e riscos;
8. indicadores executivos e critérios de aceite;
9. revisão final antes de declarar qualquer item concluído.

## Skills já disponíveis que apoiam o fluxo

| Skill | Uso no ness.OS |
|---|---|
| `verification-before-completion` | impede encerramento sem evidência recente |
| `iso27001-controls` | traduz hardening e operação em controles verificáveis |
| `context7-mcp` | consulta documentação atual de APIs e ferramentas |
| `frontend-design` / `visualize` | diagramas oficiais e painel executivo |
| `report-generator` | relatórios de saúde, risco, capacidade e projetos |
| `audit-website` / `web-perf` | mede PWA e decide objetivamente sobre CDN |
| `organization-best-practices` | papéis, tenants e isolamento de clientes |

## Skills públicas encontradas

A busca em 22/08/2026 encontrou `devops-iac-engineer` (767 instalações), `backup-disaster-recovery` (580), `database-backup-restore` (535) e `backup-restore-runbook-generator` (234). Elas podem fornecer checklists laterais, mas não devem comandar produção antes de revisão com `skill-vetter`. Nenhuma substitui a skill específica do ness.OS.

## Próxima ação

Após aprovação, gerar a skill interna a partir deste fluxo, testar primeiro sobre documentação e ambiente descartável e só depois permitir que ela conduza gates operacionais.
