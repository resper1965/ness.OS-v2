#!/usr/bin/env bash
# Carga mensal de vulnerabilidades no Hub. Roda no stack (cron do agente, dia 1º) ou sob demanda.
# Para cada Wazuh: extrai com vuln-mensal.py, traz hub.csv e troca as linhas daquela origem numa transação
# (Wazuh fora do ar não apaga os outros). Uso: vuln-carga.sh [--email destino@ness.com.br]
set -euo pipefail
KEY=${KEY:-$HOME/.ssh/nessos_agent}
HUB=${HUB:-ness_admin@144.91.115.242}
WAZUH=${WAZUH:-"pool-01=ness_admin@169.58.178.187 rzk-01=ness_admin@144.91.72.202"}
DIR=$(dirname "$0")
OUT=$(mktemp -d /tmp/opencode/vuln-carga.XXXX)
trap 'rm -rf "$OUT"' EXIT
ssh_() { ssh -i "$KEY" -o BatchMode=yes "$@"; }
type psql_ >/dev/null 2>&1 || psql_() { ssh_ "$HUB" 'sudo -n docker exec -i ninf-postgres sh -c '\''psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"'\'; }

falhou=0
for par in $WAZUH; do
  src=${par%%=*} host=${par#*=}
  if ! { scp -q -i "$KEY" "$DIR/vuln-mensal.py" "$host:/tmp/vuln-mensal.py" &&
         ssh_ "$host" 'sudo -n rm -rf /tmp/vuln-hub && sudo -n python3 /tmp/vuln-mensal.py /tmp/vuln-hub >/dev/null && sudo -n cat /tmp/vuln-hub/hub.csv && sudo -n rm -rf /tmp/vuln-hub' > "$OUT/$src.csv"; }; then
    echo "$src: extração falhou, carga anterior mantida" >&2; falhou=1; continue
  fi
  { cat <<SQL
BEGIN;
CREATE TEMP TABLE stage (agent_group text, agent text, os text, package text, version text, cve text,
  severity text, cvss numeric, eol boolean, detected_at timestamptz, raw jsonb) ON COMMIT DROP;
COPY stage FROM STDIN WITH (FORMAT csv);
SQL
    cat "$OUT/$src.csv"
    cat <<SQL
\\.
DELETE FROM n_secops_vulnerabilities WHERE source = '$src';
INSERT INTO n_secops_vulnerabilities (source, customer_id, agent_group, agent, os, package, version, cve, severity, cvss, eol, detected_at, raw)
SELECT '$src', coalesce(m.customer, nullif(lower(regexp_replace(s.agent_group, '-(ESTACOES|SERVIDORES)$', '')), ''), 'sem_cliente'),
       coalesce(s.agent_group, ''), coalesce(s.agent, '—'), s.os, s.package, s.version, s.cve, s.severity, s.cvss, s.eol, s.detected_at, s.raw
FROM stage s
LEFT JOIN (SELECT DISTINCT ON (external_customer_id) external_customer_id, lower(internal_customer_id) AS customer
           FROM n_infraops_tenant_mappings WHERE external_platform = 'wazuh' ORDER BY external_customer_id, id) m
  ON m.external_customer_id = s.agent_group;
SELECT '$src: ' || count(*) || ' linhas' FROM n_secops_vulnerabilities WHERE source = '$src';
COMMIT;
SQL
  } | psql_ | grep -v '^$' || { echo "$src: carga falhou, transação desfeita" >&2; falhou=1; }
done

if [ "${1:-}" = "--email" ] && [ -n "${2:-}" ]; then
  ssh_ "$HUB" "sudo -n docker exec ninf-api python -m app.services.vuln_report '$2'"
fi
exit $falhou
