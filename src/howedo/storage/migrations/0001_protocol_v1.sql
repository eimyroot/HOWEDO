-- HOWEDO PostgreSQL schema migration: 0001_protocol_v1
-- Protocol: howedo.protocol.v1

CREATE TABLE IF NOT EXISTS howedo_schema_migrations (
    migration_id text PRIMARY KEY,
    protocol_version text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS howedo_revisions (
    resource_id text NOT NULL,
    revision text NOT NULL,
    digest text NOT NULL,
    PRIMARY KEY (resource_id, revision),
    UNIQUE (resource_id, revision, digest)
);

CREATE TABLE IF NOT EXISTS howedo_heads (
    resource_id text PRIMARY KEY,
    revision text NOT NULL,
    digest text NOT NULL,
    FOREIGN KEY (resource_id, revision, digest)
        REFERENCES howedo_revisions (resource_id, revision, digest)
);

CREATE TABLE IF NOT EXISTS howedo_witnesses (
    witness_digest text PRIMARY KEY,
    witness_kind text NOT NULL,
    protocol_version text NOT NULL,
    payload jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS howedo_events (
    sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id text NOT NULL UNIQUE,
    event_type text NOT NULL,
    resource_id text NULL,
    protocol_version text NOT NULL,
    payload jsonb NOT NULL
);

CREATE INDEX IF NOT EXISTS howedo_events_resource_sequence_idx
    ON howedo_events (resource_id, sequence)
    WHERE resource_id IS NOT NULL;

INSERT INTO howedo_schema_migrations (migration_id, protocol_version)
VALUES ('0001_protocol_v1', 'howedo.protocol.v1')
ON CONFLICT (migration_id) DO NOTHING;
