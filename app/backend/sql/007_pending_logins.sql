-- Logins recusados por falta de vínculo (ADR 0015). O admin vê aqui e vincula, sem nunca ligar por e-mail.
CREATE TABLE IF NOT EXISTS n_infraops_pending_logins (
    issuer     VARCHAR(512) NOT NULL,
    subject    VARCHAR(255) NOT NULL,
    email      VARCHAR(320),
    attempts   INTEGER NOT NULL DEFAULT 1,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (issuer, subject)
);
