# Zabbix PRD-01 — baseline de polimento offline (2026-08-25)

Executado exclusivamente contra a restauração isolada da VPS permanente. O
Zabbix Server permaneceu inativo e mascarado, sem listener `10051`, ações,
mídias ou conectores ativos.

## Foto operacional

| Métrica | Resultado |
| --- | ---: |
| Hosts monitorados | 311 |
| Templates | 362 |
| Itens habilitados | 41.806 |
| Itens não suportados | 1.204 |
| Triggers `unknown` habilitadas | 584 |
| Escalations vencidas | 1.829 |
| Hosts sem template | 20 |
| Hosts sem tag | 274 |
| Hosts com coordenadas | 245 |
| Mapas / elementos | 1 / 1 |
| Banco restaurado | 34.787.278.848 bytes |

## Ordem de tratamento

1. Corrigir os 342 timeouts locais/descobertos e o FortiGate com 344 falhas;
   consolidar um equipamento por firewall, sem inventar capacidade de disco em
   interfaces WAN.
2. Corrigir as 288 falhas Windows e sua disponibilidade de agente antes de
   alterar templates ou desativar itens.
3. Reconciliar os dois switches com template `FortiGate by HTTP` indevido.
4. Classificar os 274 hosts sem tag e os 20 sem template usando inventário
   GLPI; em seguida, evoluir os mapas e a localização dos 66 ativos restantes.
5. Tratar as 1.829 escalations históricas por política, não por limpeza direta
   no banco.

O relatório completo permanece root-only no destino em
`/var/lib/ness-os/restore-evidence/offline-polish-baseline-20260825T185012-0300.txt`.
