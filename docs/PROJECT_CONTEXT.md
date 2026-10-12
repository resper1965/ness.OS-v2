# Contexto canônico — ness.OS

Atualizado em: 2026-10-11 (BRT)  
Estado: planejamento ativo; nenhum gate é considerado aprovado sem evidência
datada e reproduzível.

## Propósito

O ness.OS é a camada operacional que reúne monitoramento, ITSM, automação e
SecOps em uma experiência segura por tenant. O primeiro produto aceito é o
fluxo autenticado:

```text
Zabbix -> incidente no Hub -> ticket GLPI -> acompanhamento e encerramento
```

Wazuh, Google Workspace, automações ampliadas e painéis executivos entram após
esse fluxo, não como pré-requisito para o MVP.

## Fontes canônicas

| Tema | Documento de referência |
| --- | --- |
| Estado do MVP e evidências recentes | `docs/execution/project-stage-2026-09-28.md` |
| Plano por ativo e gates | `docs/execution/ness-os-asset-activation-master-plan-2026-08-28.md` |
| Matriz de pendências | `docs/execution/goal-completion-audit-2026-09-08.md` |
| Recuperação e release | `docs/execution/gates/phase-0-recovery-release.md` |
| Plano de execução atual | `docs/superpowers/plans/2026-10-11-ness-os-complete-implementation-route.md` |

Documentos históricos permanecem como evidência; não substituem uma validação
atual de ambiente, credenciais, backup ou serviço.

## Estado consolidado

| Componente | Situação | Próximo gate |
| --- | --- | --- |
| Repositório e release | Git sincronizado; release ainda bloqueada pela Fase 0 | árvore limpa, CI, digests e rollback comprovados |
| Zabbix | destino permanente restaurado em UAT isolada; origem é rollback | revalidar estado atual, UAT de identidade e piloto Cavan antes de corte |
| Object Storage/Restic | restores de Zabbix, AIOps e Psono documentados | renovar prova dentro do RPO e monitorar timers |
| Hub | fluxo local e testes avançados, mas sem UAT real aceita | Authentik + Zabbix + GLPI reais, tenant e replay |
| GLPI | fundação, catálogo e reconciliação parcial prontos | API de máquina e jornada de ticket ponta a ponta |
| Authentik | base e integrações parciais | MFA, revogação e teste por aplicação/tenant |
| Psono Community | PoC funcional e recuperável na AIOps | dois custodians, MFA, SMTP/recovery e promoção dedicada |
| AIOps | backup/restore comprovados; operação ainda não homologada | contratos, fluxos de incidente e observabilidade |
| Wazuh | planejado | capacidade, arquitetura hub-spoke e piloto isolado |

## Regras permanentes

1. A origem Zabbix não é alterada durante a migração sem rollback comprovado.
2. Nenhum segredo, token, senha, chave privada ou dump entra no Git.
3. Toda alteração produtiva tem backup, rollback, owner e evidência posterior.
4. Dados de tenant só aparecem no Hub quando origem, escopo e frescor forem
   comprovados; indisponibilidade nunca vira zero ou saudável.
5. Ações corretivas, notificações, agentes, proxies e DNS só são ativados no
   gate explicitamente aprovado.
6. Branding vem após estabilidade funcional e usa a base ness.: Montserrat 500,
   caixa baixa e ponto BlueDot `#00ade8`.

## Localização do projeto

- WSL: `/home/resper/ness.OS`
- Windows: `\\wsl.localhost\\Ubuntu\\home\\resper\\ness.OS`
- Git remoto: `https://github.com/resper1965/n-infraops.git`

Arquivos temporários de execução não pertencem ao checkout. Os encontrados em
2026-10-11 foram preservados em quarentena externa, com checksum, antes da
sincronização do Git.
