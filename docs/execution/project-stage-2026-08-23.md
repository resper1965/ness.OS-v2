# Estágio executivo do projeto ness.OS — 23/08/2026

## Posição atual

O projeto está na **Fundação, Gate 0**, com recuperação local comprovada e expansão ainda bloqueada. O estado não é expresso em percentual: cada avanço depende de evidência e critério de saída.

**Marco atual:** `M0 — Gate 0` em andamento.
**Próximo marco:** `M1 — Fundação recuperável`.
**Decisão executiva:** não comprar a expansão Wazuh nem executar o cutover Zabbix enquanto M0, baseline GLPI, identidade e Gate Financeiro não estiverem satisfeitos.

## Semáforo executivo

| Estado | Frente | Evidência atual | Próxima saída obrigatória |
|---|---|---|---|
| Concluído nesta etapa | Backup e restore local | AIOps e Zabbix restaurados em isolamento; checksums aprovados | preservar artefatos e não repetir sem mudança relevante |
| Em andamento | Zabbix | cópia real restaurada e quarentenada na KVM8 | reduzir 1.204 itens unsupported, 584 triggers unknown e 1.829 escalations antes do cutover |
| Em andamento | GLPI/Governança | GLPI estável; manifesto com 5 projetos, 13 WPs e 8 categorias; validadores secos aprovados | aprovação formal, conta API nominal e piloto de catálogo/projetos/runbooks |
| Parcial | Authentik/RBAC | core saudável; Hub, GLPI, n8n e Zabbix iniciam protocolo | MFA, `platform_admin` restrito e homologação positiva/negativa por aplicação |
| Parcial | AIOps/Portal | RBAC server-side, indicadores iniciais e API Contabo GET-only preparados | ingestão real idempotente, tenant testado, projetos e saúde executiva com fonte/qualidade |
| Bloqueado externamente | Object Storage | tooling Restic/S3 versionado; configuração e Restic ausentes nos hosts verificados | endpoint HTTPS, bucket, access key, secret key, senha Restic, upload/check/restore externo |
| Bloqueado externamente | Cofre de segredos | Psono Community aprovado conceitualmente | VPS dedicada, domínio, SMTP, PoC e recuperação por duas pessoas |
| Planejado | Wazuh hub-spoke | arquitetura e ondas definidas | somente após Gate 6 e Gate Financeiro; piloto de 50–100 endpoints |
| Pendente | Go-live | hardening e critérios definidos | SLO, DR, pentest, UAT, treinamento e aceite M7 |

## Estado dos marcos

| Marco | Estado | Leitura executiva |
|---|---|---|
| M0 — Gate 0 | em andamento | restore local passou; cópia externa, identidade e segredos ainda impedem o fechamento |
| M1 — Fundação recuperável | preparado/bloqueado | depende de Psono, SOPS/age, Object Storage e infraestrutura reproduzível |
| M2 — Zabbix estabilizado | em andamento em staging | restore passou; qualidade de coleta e destino Contabo limpo impedem o corte |
| M3 — Governança operacional | preparado | estrutura GLPI existe, mas ainda não foi carregada/aprovada em produção |
| M4 — Núcleo AIOps | parcial | componentes existem; fluxo real sinal → incidente → GLPI ainda não foi aceito |
| M5 — Portal/Contabo | parcial | controle read-only existe; reconciliação completa e painel executivo real pendem |
| M6 — Segurança integrada | planejado | nenhuma compra Wazuh autorizada nesta fase |
| M7 — Go-live | pendente | depende de todos os marcos anteriores |

## Caminho crítico

```text
Object Storage + Psono/SOPS
           |
           v
      fechar Gate 0
           |
           +--> Authentik + MFA + platform_admin
           |
           +--> GLPI piloto + inventário/localização
                         |
                         v
              saneamento/cutover Zabbix
                         |
                         v
             AIOps + painel executivo real
                         |
                         v
              Gate 6 + Gate Financeiro
                         |
                         v
                  Wazuh por ondas
```

## Próximas ações objetivas

1. Contratar/configurar Contabo Object Storage e fornecer os cinco insumos secretos fora do chat; executar Restic com upload, `check` e restore isolado.
2. Provisionar a VPS dedicada do Psono Community e colocar segredos humanos no cofre; usar SOPS/age para automação.
3. Criar `platform_admin` comum (`is_superuser=false`), preparar MFA e associar exclusivamente Ricardo Esper, Ismael Araujo e Rogério Salerno após matrícula comprovada.
4. Aprovar o manifesto GLPI, criar conta API de menor privilégio e carregar primeiro as oito categorias vazias; depois os cinco projetos piloto.
5. Sanear a coleta Zabbix em ondas começando pelo FortiGate Numen, VMware e parâmetros/macros inválidos, sem iniciar o servidor de staging fora do gate aprovado.
6. Consolidar BOM datada dentro do teto de EUR 2.000/mês antes de qualquer compra Wazuh.

## Bloqueios que exigem Ricardo Esper

- liberar/contratar Object Storage e fornecer credenciais por canal seguro;
- definir domínio e SMTP do Psono e autorizar a VPS dedicada;
- aprovar formalmente o manifesto GLPI para escrita controlada;
- confirmar owners técnicos dos WPs e o tenant/50–100 endpoints do piloto;
- concluir a matrícula MFA dos três administradores-alvo.

## Evidências canônicas

- [`internal-routines-execution-2026-08-23.md`](internal-routines-execution-2026-08-23.md)
- [`gate-0-status.md`](gate-0-status.md)
- [`backup-verification-2026-08-21.md`](backup-verification-2026-08-21.md)
- [`zabbix-polish-baseline-2026-08-20.md`](zabbix-polish-baseline-2026-08-20.md)
- [`glpi-foundation-2026-08-21.md`](glpi-foundation-2026-08-21.md)
- [`../../infra/docs/authentik-integration-audit.md`](../../infra/docs/authentik-integration-audit.md)
- [`../ecosystem-completion-plan.md`](../ecosystem-completion-plan.md)
