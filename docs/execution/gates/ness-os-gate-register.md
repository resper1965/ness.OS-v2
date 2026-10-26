# Registro de gates ness.OS

Índice de retomada criado em 22/10/2026. **Não é aceite novo.** O
[indicador datado](../ness-os-status.md) prevalece; cada gate só muda com
evidência específica, owner e data. Um subteste PASS não torna a linha PASS.

| Gate | Estado neste checkpoint | Evidência a consultar / próxima condição |
|---|---|---|
| G0 — release | Parcial, sem aceite global | [gate 0](../gate-0-status.md), PRs #64/#81; checks no SHA #81 não provam signer ou runtime produtivo. |
| G1 — continuidade | Parcial, sem aceite global | Restore externo isolado pós-rotação PASS para um conjunto; conferir release, RPO/RTO e retorno aplicável antes da promoção. |
| G2 — identidade/isolamento | Aberto | MFA/recuperação nominais e negativa direta GLPI T03 pendentes; conta 106 desativada. |
| Z-M1–Z-M4 | Checkpoints individuais não reavaliados aqui | [estágio Zabbix](../project-stage-2026-10-12.md) e [plano Zabbix](../../superpowers/plans/2026-10-12-zabbix-fluid-delivery.md); não inferir estado por esta linha. |
| Z-M5 — corte Zabbix | Não aprovado | Janela/token expirados; coleta, SSO, freeze, GO, rollback e origem parada antes do destino são obrigatórios. |
| G3 — Hub/PWA | Não aprovado | Jornada real por tenant/papel e runtime por digest ainda sem aceite global. |
| G4 — operação integrada | Não aprovado | Evento→incidente→ticket, replay/timeout, negativa cruzada e expansão por ondas pendentes. |
| G5 — segurança produtiva | Não aprovado | Wazuh/Workspace exigem capacidade, isolamento, recuperação e aceite por faixa. |

Para qualquer mudança, acrescentar registro datado no documento de execução
da frente e atualizar o [indicador](../ness-os-status.md). Não marcar PASS
neste índice sem evidência/readback e decisão do owner aplicável. A
[entrada para outro desenvolvedor](../developer-handoff-2026-10-22.md)
explica checkout, PRs e bloqueios atuais.
