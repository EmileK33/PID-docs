-- Mounted into the Postgres fixture at /docker-entrypoint-initdb.d/ so the
-- extension is present on first boot. pgcrypto provides gen_random_uuid(),
-- which the schema relies on for primary keys (spec §1.2).
CREATE EXTENSION IF NOT EXISTS pgcrypto;
