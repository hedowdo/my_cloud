"""Initial metadata schema; no credentials or application user accounts seeded."""

from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE users (
            id uuid PRIMARY KEY,
            email text NOT NULL,
            email_key text NOT NULL UNIQUE,
            password_hash text NOT NULL,
            role text NOT NULL CHECK (role IN ('admin', 'member')),
            active boolean NOT NULL DEFAULT true,
            theme text NOT NULL DEFAULT 'light' CHECK (theme IN ('light', 'dark')),
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE sessions (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL REFERENCES users(id),
            token_hash bytea NOT NULL UNIQUE CHECK (octet_length(token_hash) = 32),
            csrf_hash bytea NOT NULL CHECK (octet_length(csrf_hash) = 32),
            created_at timestamptz NOT NULL DEFAULT now(),
            last_seen_at timestamptz NOT NULL DEFAULT now(),
            idle_expires_at timestamptz NOT NULL,
            absolute_expires_at timestamptz NOT NULL,
            revoked_at timestamptz
        );
        CREATE INDEX sessions_user_idx ON sessions(user_id);
        CREATE TABLE invitations (
            id uuid PRIMARY KEY,
            token_hash bytea NOT NULL UNIQUE CHECK (octet_length(token_hash) = 32),
            created_by uuid NOT NULL REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            redeemed_at timestamptz,
            redeemed_by uuid REFERENCES users(id),
            revoked_at timestamptz,
            CHECK (expires_at > created_at),
            CHECK ((redeemed_at IS NULL) = (redeemed_by IS NULL))
        );
        CREATE TABLE blobs (
            id uuid PRIMARY KEY,
            storage_key text NOT NULL UNIQUE CHECK (storage_key ~ '^[a-f0-9]{64}$'),
            size_bytes bigint NOT NULL CHECK (size_bytes >= 0 AND size_bytes <= 500000000),
            checksum_sha256 text NOT NULL CHECK (checksum_sha256 ~ '^[a-f0-9]{64}$'),
            media_type text NOT NULL DEFAULT 'application/octet-stream'
                CHECK (length(media_type) BETWEEN 1 AND 255),
            state text NOT NULL CHECK (state IN ('staging', 'durable', 'deleting')),
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE items (
            id uuid PRIMARY KEY,
            parent_id uuid REFERENCES items(id),
            kind text NOT NULL CHECK (kind IN ('file', 'folder')),
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 255),
            name_key text NOT NULL CHECK (length(name_key) > 0),
            uploader_id uuid REFERENCES users(id),
            blob_id uuid REFERENCES blobs(id),
            icon_blob_id uuid REFERENCES blobs(id),
            revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            trashed_at timestamptz,
            trashed_by uuid REFERENCES users(id),
            replacement_of uuid REFERENCES items(id),
            CHECK (parent_id IS DISTINCT FROM id),
            CHECK ((kind = 'file' AND blob_id IS NOT NULL) OR
                   (kind = 'folder' AND blob_id IS NULL)),
            CHECK ((id = '00000000-0000-0000-0000-000000000001' AND
                    parent_id IS NULL AND kind = 'folder' AND trashed_at IS NULL) OR
                   (id <> '00000000-0000-0000-0000-000000000001' AND parent_id IS NOT NULL))
        );
        CREATE UNIQUE INDEX items_live_name_idx ON items(parent_id, name_key)
            WHERE trashed_at IS NULL;
        CREATE INDEX items_parent_idx ON items(parent_id);
        CREATE INDEX items_uploader_date_idx ON items(uploader_id, created_at);
        INSERT INTO items (id, kind, name, name_key)
            VALUES ('00000000-0000-0000-0000-000000000001', 'folder', '/', '/');
        CREATE TABLE positions (
            item_id uuid PRIMARY KEY REFERENCES items(id),
            x double precision NOT NULL CHECK (x BETWEEN -1000000 AND 1000000),
            y double precision NOT NULL CHECK (y BETWEEN -1000000 AND 1000000),
            revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0),
            updated_by uuid NOT NULL REFERENCES users(id),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE activity (
            id uuid PRIMARY KEY,
            actor_id uuid NOT NULL REFERENCES users(id),
            action text NOT NULL CHECK (action IN ('upload', 'download', 'rename', 'move',
                'folder_create', 'replace', 'trash', 'restore', 'permanent_delete',
                'icon_update', 'invitation_create', 'invitation_revoke', 'user_deactivate')),
            target_id uuid NOT NULL,
            target_name text NOT NULL,
            occurred_at timestamptz NOT NULL DEFAULT now(),
            request_id uuid NOT NULL,
            details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details) = 'object')
        );
        CREATE INDEX activity_time_idx ON activity(occurred_at DESC, id);
        CREATE INDEX activity_actor_idx ON activity(actor_id, occurred_at DESC);
        CREATE TABLE upload_reservations (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL REFERENCES users(id),
            parent_id uuid NOT NULL REFERENCES items(id),
            blob_id uuid REFERENCES blobs(id),
            reserved_bytes bigint NOT NULL CHECK (reserved_bytes BETWEEN 0 AND 500000000),
            received_bytes bigint NOT NULL DEFAULT 0,
            state text NOT NULL CHECK (state IN ('reserved', 'streaming', 'finalizing',
                'complete', 'aborted')),
            expires_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CHECK (received_bytes BETWEEN 0 AND reserved_bytes)
        );
        CREATE INDEX reservations_expiry_idx ON upload_reservations(state, expires_at);
        CREATE TABLE namespace_lock (
            id integer PRIMARY KEY CHECK (id = 1)
        );
        INSERT INTO namespace_lock (id) VALUES (1);
    """)


def downgrade() -> None:
    # Development rehearsal only; production rollback requires a verified backup and approval.
    op.execute("""
        DROP TABLE namespace_lock;
        DROP TABLE upload_reservations;
        DROP TABLE activity;
        DROP TABLE positions;
        DROP TABLE items;
        DROP TABLE blobs;
        DROP TABLE invitations;
        DROP TABLE sessions;
        DROP TABLE users;
    """)
