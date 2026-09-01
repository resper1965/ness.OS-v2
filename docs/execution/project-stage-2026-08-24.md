# Estágio executivo do projeto ness.OS — 24/08/2026

## Posição atual

O ness.OS permanece em **M0 — Gate 0**, agora com backups locais e externos recuperáveis aprovados para Zabbix e AIOps. Os bloqueios de saída remanescentes são o cofre definitivo e a identidade ponta a ponta. Não há percentual artificial; o avanço é medido por evidência de cada gate.

## Semáforo

| Estado | Frente | Evidência de hoje | Próxima saída |
|---|---|---|---|
| Aprovado ponta a ponta | Backup/restore | AIOps e Zabbix com backup local, Object Storage, `check`, restore externo e checksums aprovados | operar timers e acompanhar retenção |
| Em andamento | Zabbix | cópia restaurada preservada na KVM8; nova Contabo permanente aprovada | polimento de coleta, compra/provisionamento e cutover direto com rollback preservado |
| Em andamento | GLPI/Governança | manifesto aprovado; perfil mínimo ID 12, usuário técnico ID 94 e tokens criados | liberar caminho de máquina da API, dry-run remoto e carga das oito categorias |
| Parcial | Authentik/RBAC | login humano do GLPI funciona; API é interceptada pelo SSO | rota privada ou exceção estrita de API; MFA e `platform_admin` homologados |
| Parcial | AIOps/Portal | SSH nominal recuperado, backup externo ativo e código/integrações preparados | testar GLPI e Authentik ponta a ponta |
| Contenção temporária | Segredos | credenciais GLPI rotacionadas e guardadas em arquivo local ignorado pelo Git, `0600` | Psono Community para humanos e SOPS/age para automação; nova rotação no go-live |
| Aprovado | Object Storage | bucket privado, usuário S3 nominal/2FA, Restic, timers, uploads, checks e restores aprovados | monitorar jobs e capacidade |
| Planejado | Wazuh hub-spoke | arquitetura escalonada definida | piloto após Gate 6 e Gate Financeiro |

## Decisões e achados de hoje

- A gestão global continua restrita a Ricardo Esper, Ismael Araujo e Rogério Salerno por meio do futuro grupo `platform_admin`; a existência das contas não substitui MFA e testes negativos.
- O GLPI não recebeu carga de catálogo ou projetos. O teste de `initSession` foi interrompido pelo redirecionamento `302` do Authentik, portanto a API de máquina ainda não está funcional.
- O caminho preferido é AIOps → GLPI por rede privada. Se for usada exceção no proxy, ela deve cobrir apenas a API e manter tokens, origem efetiva, rate limit e logs.
- A primeira geração das credenciais GLPI foi invalidada após expansão indevida em retorno local. A segunda geração está protegida, mas também será substituída no gate final.
- A nova Contabo foi aprovada como VPS permanente do Zabbix; a origem será rollback por 7–14 dias e depois, após reimage, será reaproveitada no piloto Wazuh. A ficha de aquisição está em [`../procurement/zabbix-contabo-permanent-spec-2026-08-24.md`](../procurement/zabbix-contabo-permanent-spec-2026-08-24.md).
- A baseline offline automatizada da KVM8 confirmou isolamento e quantificou 1.204 itens não suportados, 584 triggers `unknown`, 1.829 escalations vencidas e banco de 34.574.450.688 bytes, sem expor erros brutos ou segredos.
- A Onda A identificou 58 erros de cálculo FortiGate em hosts de link WAN correspondentes a 35 appliances candidatos. Como o upstream Zabbix 7.0 mantém a mesma fórmula, o plano aprovado corrige a modelagem para um host por firewall e descoberta de interfaces; não falsifica capacidade zero.
- A Onda B isolou 32 erros em dois ativos `SW01-...-Core` que possuem somente o template FortiGate HTTP. A correção passou a ser reconciliação GLPI e troca do template por classe/modelo, não ajuste em massa de JSONPath.

## Próximos passos executáveis

1. Definir o caminho privado da API GLPI e testar `initSession`, leituras mínimas, `killSession` e origem negativa a partir da AIOps.
2. Executar o dry-run remoto do manifesto; após aceite, carregar somente as oito categorias vazias e provar idempotência.
3. Implantar Psono Community/SOPS-age, migrar consumidores e rotacionar novamente todos os valores temporários.
4. Executar a Onda A FortiGate no UAT da nova VPS: um appliance piloto, dois ou mais links, paridade por 24–72 horas e rollback sem `unlink and clear`.
5. Reconciliar no GLPI os dois ativos da Onda B e homologar o template correto no mesmo UAT.
6. Contratar e provisionar a nova VPS Contabo permanente do Zabbix; repetir restore/UAT antes do corte.
7. Preservar a VPS atual por 7–14 dias e, após aceite/reimage, reutilizá-la no piloto Wazuh.

## Evidências relacionadas

- [`glpi-foundation-2026-08-21.md`](glpi-foundation-2026-08-21.md)
- [`gate-0-status.md`](gate-0-status.md)
- [`secret-rotation-plan-2026-08-22.md`](secret-rotation-plan-2026-08-22.md)
- [`backup-verification-2026-08-21.md`](backup-verification-2026-08-21.md)
- [`contabo-object-storage-action-required-2026-08-24.md`](contabo-object-storage-action-required-2026-08-24.md)
- [`../../infra/docs/authentik-integration-audit.md`](../../infra/docs/authentik-integration-audit.md)
