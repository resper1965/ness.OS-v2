-- Additive compatibility change. Apply before writing reconciled assets.
-- Keep this enum value and the matching Python enum on application rollback;
-- do not relabel an unknown operating system as Linux to contract the schema.
ALTER TYPE asset_type ADD VALUE IF NOT EXISTS 'unknown';
