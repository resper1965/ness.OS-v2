# GLPI T05 — três ativos criados (02/11/2026)

OK do Ricardo em 02/11 para criar os 3 Computers na entidade 1 (Alupar). Host AIOps `144.91.115.242`.

| Passo | Resultado |
| --- | --- |
| Dry-run `cmdb_sync --hostids 10983 10984 10987` | 3 × `missing_glpi`, entidade 1, sem candidato por nome |
| Criação pela API com a credencial do Hub (94) | `ERROR_GLPI_ADD`: sem permissão. O Hub não escreve no cadastro mestre (desenho); nada gravado |
| Estado anterior (leitura) | 103 Computers, 0 excluídos, id máx. 107, 0 marcadores `10983/10984/10987`, 0 nomes iguais |
| Backup | `glpi_computers` + `glpi_logs` em `/opt/n-infraops/rollback/glpi-t05-20261102/` (12 MB); backup noturno do AIOps rodou 16 h antes |
| Criação | `infra/scripts/glpi-hub-complete-inventory.php --apply` no contêiner `ninf-glpi` (como `www-data`, `callAsSystem`), plano com só os 3 gaps → Computers 108, 109, 110, entidade 1, `is_recursive=0` |
| Repetição | segunda execução não criou nada; total 106 |
| Dry-run depois | `mapped_assets=3`, `gaps=[]` |

Sem serial, owner, criticidade ou hardware inventados. Comentário `Zabbix Host ID: <id>` é o marcador de identidade.

Rollback: exclusão lógica dos ids 108–110 (sem purge) ou restauração das tabelas do dump acima.

Falta: `cmdb_sync --apply --hostids …` (cria os `Asset` no Hub e liga os incidentes históricos) — decisão do Ricardo.
