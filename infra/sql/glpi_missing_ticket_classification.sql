-- Read-only operational classification; no incident payload or fingerprint leaves DB.
WITH missing AS (
    SELECT i.id, i.status, i.created_at, i.tags,
           a.action AS last_glpi_action,
           a.note AS last_glpi_note
    FROM n_infraops_incidents AS i
    LEFT JOIN LATERAL (
        SELECT action, note
        FROM n_infraops_incident_actions
        WHERE incident_id = i.id AND actor_source = 'glpi'
        ORDER BY id DESC
        LIMIT 1
    ) AS a ON true
    WHERE i.deskmanager_ticket_id IS NULL
), classified AS (
    SELECT status,
           CASE
               WHEN tags ->> 'ninf_zabbix_event_id' IS NULL THEN 'source_id_missing'
               WHEN last_glpi_action = 'ticket_failed'
                    AND last_glpi_note LIKE 'error=GLPIPermanentError%' THEN 'permission_denied'
               WHEN last_glpi_action = 'ticket_failed' THEN 'delivery_failed_unclassified'
               WHEN created_at >= now() - interval '10 minutes' THEN 'recent_no_ticket'
               ELSE 'no_failure_record'
           END AS cause,
           created_at
    FROM missing
)
SELECT status, cause, count(*) AS incidents,
       date_trunc('day', min(created_at))::date AS oldest_day_utc,
       date_trunc('day', max(created_at))::date AS newest_day_utc
FROM classified
GROUP BY status, cause
ORDER BY incidents DESC, status, cause;

SELECT CASE
           WHEN a.note LIKE 'error=%' THEN split_part(a.note, '=', 2)
           ELSE 'none'
       END AS latest_error_type,
       count(*) AS recent_missing_tickets
FROM n_infraops_incidents AS i
LEFT JOIN LATERAL (
    SELECT note
    FROM n_infraops_incident_actions
    WHERE incident_id = i.id AND actor_source = 'glpi'
    ORDER BY id DESC
    LIMIT 1
) AS a ON true
WHERE i.deskmanager_ticket_id IS NULL
  AND i.created_at >= now() - interval '24 hours'
GROUP BY latest_error_type
ORDER BY recent_missing_tickets DESC;

SELECT date_trunc('hour', i.created_at) AS created_hour_utc,
       count(*) AS missing_tickets,
       count(DISTINCT i.host_id) AS distinct_hosts,
       count(DISTINCT i.trigger_id) AS distinct_triggers
FROM n_infraops_incidents AS i
WHERE i.deskmanager_ticket_id IS NULL
  AND i.created_at >= now() - interval '24 hours'
GROUP BY created_hour_utc
ORDER BY created_hour_utc;
