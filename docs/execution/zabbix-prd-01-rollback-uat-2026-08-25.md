# Zabbix PRD-01 — rollback UAT e corte (2026-08-25)

## Ponto de recuperação comprovado

- Restore local aprovado: backup `20260822T121154-0300`.
- Backup offline do destino: `20260825T202327-0300`.
- Cópia Restic externa verificada: snapshot `60a22d18`.
- A VPS atual permanece intacta como rollback operacional por 7–14 dias após o
  futuro corte.

## Rollback antes do corte

1. Não alterar DNS, proxy ou agente antes de exportar a configuração via API
   suportada e confirmar o arquivo de rollback.
2. Para piloto de template, usar apenas `Unlink` sem `clear`; manter o vínculo
   anterior e o host legado durante a comparação.
3. Se a UAT falhar, mascarar o novo Zabbix Server, interromper a UAT e manter a
   VPS atual como origem de coleta.

## Rollback após o corte

1. Reverter DNS/acesso para a VPS atual e interromper o novo servidor.
2. Reverter proxies/agentes pelo conjunto documentado, sem limpeza de histórico
   na nova VPS.
3. Preservar ambos os bancos e snapshots; abrir incidente de mudança e anexar
   evidências antes de qualquer nova tentativa.

## Condições ainda necessárias

- autenticação OIDC/MFA e contas administrativas homologadas;
- export API de hosts/templates e verificação por owner/GLPI;
- aceite UAT da Onda 1 por 24–72 horas;
- decisão explícita de início de coleta e janela de corte.
