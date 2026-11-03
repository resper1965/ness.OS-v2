# GLPI T06 — onda 1: cinco ativos criados (03/11/2026)

OK do Ricardo em 03/11 ("os ativos serão gerenciados lá"). Host AIOps `144.91.115.242`. Segunda exceção à regra do plano (linha 19) para o `callAsSystem`, a mesma da T05, só para esta criação. Manifesto: [glpi-t06-manifest-2026-11-03.md](glpi-t06-manifest-2026-11-03.md).

| Passo | Resultado |
| --- | --- |
| Estado anterior (leitura) | 106 Computers (id máx. 110), 156 NetworkEquipments (id máx. 156); 0 marcadores `10985/10988/10991/10992/10996`; 0 nomes iguais |
| Plano | `cmdb_sync --hostids …` (5 × `missing_glpi`), revisado à mão com `itemtype` por gap (o `cmdb_sync` não emite esse campo): 10988 = NetworkEquipment (Fortigate), demais = Computer |
| Backup | `glpi_computers` + `glpi_networkequipments` + `glpi_logs` em `/opt/n-infraops/rollback/glpi-t06-20261103/dump.sql` (98 MB, sha256 `7f11cb6f…`) |
| Criação | `glpi-hub-complete-inventory.php --apply` como `www-data`: Computers 111 (10985), 112 (10991), 113 (10992), 114 (10996), todos entidade 12 (Unimed); NetworkEquipment 157 (10988), entidade 1 (Alupar); `is_recursive=0` |
| Repetição | nada criado |
| Depois | dry-run `mapped_assets=5`, `gaps=[]`; 110 Computers e 157 NetworkEquipments |

O script ganhou o campo `itemtype` do plano: classificação explícita vence a heurística por tag/nome (estes hosts não têm tag `role`).

Sem serial, owner ou criticidade inventados. Comentário `Zabbix Host ID: <id>` é o marcador.

Rollback: só Computers 111–114 e NetworkEquipment 157 (nunca o dump inteiro), depois de provar que não têm edição posterior em `glpi_logs`, ticket nem vínculo `Item_Ticket`. Se o timer do `cmdb_sync` já gravou `glpi_itemtype`/`glpi_item_id` nos assets do Hub, limpar essas referências no Hub também. Tabelas filhas (`glpi_logs` da criação, networkports, infocoms): conferir se há linhas antes de excluir; a exclusão do GLPI é soft-delete até purgar.

## Fora desta onda

- 10997 (Fortigate 60F, Nova Energia): entidade a decidir.
- Vínculo `Item_Ticket` dos ~490 incidentes: precisa de nova autorização (o OK da T05 valia só para aquele lote).
- Exceções sem host de origem: 50001, 50004–50006, 10001, 10978 e 1 incidente sem `host_id`.
