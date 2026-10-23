"""Durable upload intents and explicitly requested permanent-deletion jobs."""

from alembic import op

revision = "0003_files"
down_revision = "0002_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE deletion_jobs (
            id uuid PRIMARY KEY,
            target_id uuid NOT NULL,
            target_name text NOT NULL,
            actor_id uuid NOT NULL REFERENCES users(id),
            request_id uuid NOT NULL,
            blob_ids uuid[] NOT NULL DEFAULT '{}',
            item_count integer NOT NULL CHECK (item_count > 0),
            state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','complete')),
            last_error text CHECK (last_error IN ('storage_unavailable')),
            created_at timestamptz NOT NULL DEFAULT now(),
            completed_at timestamptz
        );
        ALTER TABLE items ADD COLUMN deletion_job_id uuid REFERENCES deletion_jobs(id);
        CREATE INDEX items_deletion_idx ON items(deletion_job_id);
        ALTER TABLE upload_reservations ADD COLUMN intent jsonb NOT NULL DEFAULT '{}'
            CHECK (jsonb_typeof(intent)='object');
        ALTER TABLE upload_reservations DROP CONSTRAINT upload_reservations_parent_id_fkey;
        ALTER TABLE upload_reservations ADD CONSTRAINT upload_reservations_parent_id_fkey
            FOREIGN KEY (parent_id) REFERENCES items(id) ON DELETE CASCADE;
        ALTER TABLE upload_reservations DROP CONSTRAINT upload_reservations_blob_id_fkey;
        ALTER TABLE upload_reservations ADD CONSTRAINT upload_reservations_blob_id_fkey
            FOREIGN KEY (blob_id) REFERENCES blobs(id) ON DELETE SET NULL;
        ALTER TABLE items DROP CONSTRAINT items_replacement_of_fkey;
        ALTER TABLE items ADD CONSTRAINT items_replacement_of_fkey
            FOREIGN KEY (replacement_of) REFERENCES items(id) ON DELETE SET NULL;
    """)


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM deletion_jobs)
        OR EXISTS (SELECT 1 FROM upload_reservations WHERE intent<>'{}'::jsonb)
        THEN RAISE EXCEPTION 'File lifecycle data exists; restore an approved backup';
        END IF; END $$;
        ALTER TABLE items DROP CONSTRAINT items_replacement_of_fkey;
        ALTER TABLE items ADD CONSTRAINT items_replacement_of_fkey
            FOREIGN KEY (replacement_of) REFERENCES items(id);
        ALTER TABLE upload_reservations DROP CONSTRAINT upload_reservations_blob_id_fkey;
        ALTER TABLE upload_reservations ADD CONSTRAINT upload_reservations_blob_id_fkey
            FOREIGN KEY (blob_id) REFERENCES blobs(id);
        ALTER TABLE upload_reservations DROP CONSTRAINT upload_reservations_parent_id_fkey;
        ALTER TABLE upload_reservations ADD CONSTRAINT upload_reservations_parent_id_fkey
            FOREIGN KEY (parent_id) REFERENCES items(id);
        ALTER TABLE upload_reservations DROP COLUMN intent;
        ALTER TABLE items DROP COLUMN deletion_job_id;
        DROP TABLE deletion_jobs;
    """)
