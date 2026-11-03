# GLPI T06 — manifesto dos hosts sem ativo (03/11/2026)

Só leitura (Hub, Zabbix e dry-run do `cmdb_sync`). Nada foi escrito no GLPI.
Os 510 incidentes sem `asset_id` no Hub estão em 13 `host_id`.

| Host | Nome | Incidentes (c/ ticket) | Zabbix | Classe | Entidade | Situação |
|---|---|---:|---|---|---:|---|
| 10985 | Unimed Salto, ESXi 01, `US-FL-01` | 201 (201) | ativo | VM / servidor | 12 | `missing_glpi` |
| 10988 | Alupar Matriz, Fortigate 200E, link Avato | 118 (115) | ativo | firewall (NetworkEquipment) | 1 | `missing_glpi` |
| 10996 | Unimed Itu, `UI-SENIORPROD` | 105 (105) | ativo | VM / servidor | 12 | `missing_glpi` |
| 10991 | Unimed Itu, `VMQLIK` | 63 (63) | ativo | VM / servidor | 12 | `missing_glpi` |
| 10997 | Nova Energia Matriz, Fortigate 60F, link Vivo | 11 (11) | ativo | firewall | a resolver | sem entidade/cliente claro no dry-run |
| 10992 | Unimed Salto, `UI-AD-01` | 6 (6) | ativo | VM / servidor (AD) | 12 | `missing_glpi` |
| 50001, 50004–50006 | `WAN-Core-01/04/05/06` | 8 (4) | **não existe mais** | desativado | — | exceção explícita: sem host de origem |
| 10001 | `web-server-01` | 1 (1) | **não existe mais** | desativado/teste | — | exceção explícita |
| 10978 | `uat-synthetic-alerts` | 1 (1) | ativo, `scope=uat` | sintético | — | não é equipamento; fora da contagem |
| (vazio) | sem `host_id` | 1 (1) | — | — | — | investigar o incidente |

## Leitura

- 5 hosts são ativos reais que faltam no GLPI (10985, 10988, 10996, 10991, 10992): **4 Unimed (entidade 12) e 1 Alupar (entidade 1)**. Cobrem 493 dos 510 incidentes.
- 10997 também cobre 11 incidentes, mas o `cmdb_sync` não o incluiu no dry-run (sem IP principal): precisa de decisão de entidade antes de criar.
- Criar no GLPI é escrita em cliente: a criação pela API do Hub é negada por desenho (`ERROR_GLPI_ADD`), e o script de sistema foi exceção do Ricardo só para o lote da T05. Cada onda da T06 precisa de nova autorização ou de caminho pela identidade de manutenção.
- Lotes de até 5 registros (regra do plano). Os 5 ativos reais cabem em um lote.

## Próximo

Aguardar decisão do Ricardo: criar o lote 10985/10988/10996/10991/10992 por script de sistema (nova exceção) ou ampliar o gateway de manutenção.
