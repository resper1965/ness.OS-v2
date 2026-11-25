#!/usr/bin/env bash
# Fecha chamados de alerta antigos do GLPI que ninguém tocou. Roda no host do Hub, como root.
#   glpi-limpeza-fila.sh           só conta (padrão)
#   glpi-limpeza-fila.sh --apply   fecha (status 6) em lotes; faça o backup do GLPI antes
# Candidato: status 1, título [n.infraops:…], sem técnico, sem acompanhamento humano,
# com mais de 24 h e fora dos vínculos abertos do Hub (n_infraops_ticket_links).
# Grava direto no banco de propósito: pela API cada chamado dispararia o webhook de resolução.
set -euo pipefail
APPLY=${1:-}
sql() { docker exec -i ninf-glpi-db sh -c 'mysql -N -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' 2>&1 | grep -v Warning || true; }
IDS=$(echo "select coalesce(string_agg(ticket_id::text,','),'0') from n_infraops_ticket_links where state='open'" |
  docker exec -i ninf-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At')
WHERE="t.is_deleted=0 AND t.status=1 AND t.name LIKE '[n.infraops:%' AND t.date < NOW() - INTERVAL 1 DAY
 AND t.id NOT IN ($IDS)
 AND NOT EXISTS (SELECT 1 FROM glpi_tickets_users u WHERE u.tickets_id=t.id AND u.type=2)
 AND NOT EXISTS (SELECT 1 FROM glpi_itilfollowups f WHERE f.itemtype='Ticket' AND f.items_id=t.id AND f.users_id<>(SELECT id FROM glpi_users WHERE name='svc_ness_os'))"
echo "candidatos: $(echo "SELECT COUNT(*) FROM glpi_tickets t WHERE $WHERE" | sql)"
[ "$APPLY" = "--apply" ] || { echo "só contagem; use --apply após backup e autorização"; exit 0; }
while :; do
  n=$(echo "UPDATE glpi_tickets t SET status=6, solvedate=NOW(), closedate=NOW(), date_mod=NOW() WHERE $WHERE LIMIT 2000; SELECT ROW_COUNT();" | sql | tail -1)
  echo "lote: $n"; [ "${n:-0}" -gt 0 ] || break
done
echo "restantes: $(echo "SELECT COUNT(*) FROM glpi_tickets t WHERE $WHERE" | sql)"
