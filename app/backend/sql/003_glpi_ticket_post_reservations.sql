-- Durable, one-shot permission to POST a GLPI ticket for an entity/event.
-- Keep rows across retries and rollbacks; reconcile ambiguous outcomes before
-- an operator removes a reservation after proving no ticket was created.
CREATE TABLE n_infraops_glpi_ticket_post_reservations (
    entity_id   INTEGER NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (entity_id, fingerprint)
);
