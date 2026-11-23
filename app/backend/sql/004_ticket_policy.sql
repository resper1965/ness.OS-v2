-- Regra de abertura de chamados (spec 2026-11-15): listas editáveis sem deploy e
-- vínculo chave de dedup -> chamado GLPI (substitui a busca por marcador no título).
CREATE TABLE IF NOT EXISTS n_infraops_ticket_rules (
    id      SERIAL PRIMARY KEY,
    kind    VARCHAR(16) NOT NULL CHECK (kind IN ('action', 'noise', 'cause')),
    pattern TEXT NOT NULL,
    note    TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (kind, pattern)
);
CREATE TABLE IF NOT EXISTS n_infraops_ticket_links (
    entity_id   INTEGER NOT NULL,
    dedup_key   VARCHAR(64) NOT NULL,
    ticket_id   INTEGER NOT NULL,
    state       VARCHAR(16) NOT NULL DEFAULT 'open'
        CHECK (state IN ('open', 'auto_closed', 'closed')),
    occurrences INTEGER NOT NULL DEFAULT 1,
    last_seen   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at   TIMESTAMPTZ,
    -- Zabbix resolveu com técnico no chamado: comentado uma vez, chamado segue aberto.
    source_resolved_at TIMESTAMPTZ,
    PRIMARY KEY (entity_id, dedup_key)
);
CREATE INDEX IF NOT EXISTS ix_incidents_ticket_pending ON n_infraops_incidents ((tags->>'ninf_ticket_state'))
    WHERE tags->>'ninf_ticket_state' = 'pending';
CREATE INDEX IF NOT EXISTS ix_incidents_active_site ON n_infraops_incidents ((tags->>'ninf_site'))
    WHERE tags->>'ninf_site' IS NOT NULL AND tags->>'ninf_zabbix_status' = 'problem';
CREATE INDEX IF NOT EXISTS ix_incidents_dedup_key ON n_infraops_incidents ((tags->>'ninf_dedup_key'))
    WHERE tags->>'ninf_dedup_key' IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_incidents_cause ON n_infraops_incidents ((tags->>'ninf_cause_incident_id'))
    WHERE tags->>'ninf_cause_incident_id' IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_incidents_ticket_followup ON n_infraops_incidents ((tags->>'ninf_ticket_state'))
    WHERE tags->>'ninf_ticket_state' IN ('attached', 'symptom') AND tags->>'ninf_notified' IS NULL;
INSERT INTO n_infraops_ticket_rules (kind, pattern, note) VALUES
    ('noise', 'updater|AppXSvc|AppX Deployment|GoogleVssProvider|brave|Inventory and Compatibility Appraisal|User Access Logging', 'serviços de atualização do Windows'),
    ('noise', 'Memory Pages/sec|privileged time|queue length|request responses are too high|page table entries|Disk is overloaded', 'desempenho fino'),
    ('noise', 'Operating system description has changed|Host has been restarted', 'mudança informativa'),
    ('noise', 'sem coleta SNMP|firmware', 'pendência de configuração'),
    ('noise', 'High ICMP ping (response time|loss)|High packets loss|High error rate|High bandwidth usage', 'oscilação de rede'),
    ('action', 'Space is low|Space is critically low|disk.*full|FS \[', 'disco'),
    ('action', 'Unavailable by ICMP|agent is not available|no data', 'disponibilidade'),
    ('action', 'Tunnel down|Health check state is dead|link down|Link .* down|Interface .* down|BGP|OSPF', 'rede/link'),
    ('action', 'High memory utilization|High CPU utilization|High swap space', 'capacidade sustentada'),
    ('action', 'is not running', 'serviço de negócio (ruído vence antes)'),
    ('action', 'HTTP|web scenario|IntraNESS', 'aplicação'),
    ('cause', 'Tunnel down|Health check state is dead|link down|Link .* down|Interface .* down', 'queda de link'),
    ('cause', 'FortiGate: Unavailable by ICMP', 'gateway fora')
ON CONFLICT (kind, pattern) DO NOTHING;
INSERT INTO n_infraops_platform_params (key, value_int) VALUES
    ('ticket_grace_minutes', 15),
    ('ticket_reopen_hours', 24),
    ('ticket_symptom_lead_minutes', 2)
ON CONFLICT (key) DO NOTHING;
