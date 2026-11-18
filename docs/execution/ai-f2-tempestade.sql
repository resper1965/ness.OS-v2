-- Tempestade de alertas por cliente, últimos 30 dias (só leitura, um SELECT).
-- Para que serve: decidir se a repetição (F2) basta ou se a F3 precisa sugerir agrupamento.
-- Como rodar: psql -f ai-f2-tempestade.sql, com conta só de leitura, no banco do Hub.
-- Como ler: burst_10m perto de incidents = há tempestade (o investigador da F3 deve
-- sugerir agrupamento); caso contrário, a repetição basta.
--   incidents           total de incidentes do cliente
--   burst_10m           com outro incidente do mesmo cliente nos 10 min anteriores
--   same_host_30m       idem, mesmo host_id, em 30 min
--   repeat_same_trigger idem, mesmo host_id e trigger_id, em qualquer intervalo,
--                       com a raiz ainda sem glpi_resolved_at (ou resolvida depois)
WITH i AS (
  SELECT id, host_id, trigger_id, first_seen,
         COALESCE(tags ->> 'ninf_customer_name', '(sem cliente)') AS customer
  FROM n_infraops_incidents
  WHERE first_seen >= now() - interval '30 days'
)
SELECT
  i.customer,
  count(*) AS incidents,
  count(*) FILTER (WHERE EXISTS (
    SELECT 1 FROM n_infraops_incidents o
    WHERE COALESCE(o.tags ->> 'ninf_customer_name', '(sem cliente)') = i.customer
      AND (o.first_seen, o.id) < (i.first_seen, i.id)
      AND o.first_seen >= i.first_seen - interval '10 minutes'
  )) AS burst_10m,
  count(*) FILTER (WHERE EXISTS (
    SELECT 1 FROM n_infraops_incidents o
    WHERE o.host_id = i.host_id
      AND (o.first_seen, o.id) < (i.first_seen, i.id)
      AND o.first_seen >= i.first_seen - interval '30 minutes'
  )) AS same_host_30m,
  count(*) FILTER (WHERE EXISTS (
    SELECT 1 FROM n_infraops_incidents o
    WHERE o.host_id = i.host_id
      AND o.trigger_id = i.trigger_id
      AND (o.first_seen, o.id) < (i.first_seen, i.id)
      AND CASE
            WHEN o.tags ->> 'glpi_resolved_at' IS NULL THEN true
            WHEN o.tags ->> 'glpi_resolved_at' ~ '^\d{4}-\d{2}-\d{2}T'
              THEN CAST(o.tags ->> 'glpi_resolved_at' AS timestamptz) > i.first_seen
            ELSE false
          END
  )) AS repeat_same_trigger
FROM i
GROUP BY i.customer
ORDER BY burst_10m DESC, i.customer;
