"""Keep active byte/slot reservations alive when their destination is deleted."""

from alembic import op

revision = "0004_transfer_parents"
down_revision = "0003_files"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE upload_reservations DROP CONSTRAINT upload_reservations_parent_id_fkey;
        ALTER TABLE upload_reservations ALTER COLUMN parent_id DROP NOT NULL;
        ALTER TABLE upload_reservations ADD CONSTRAINT upload_reservations_parent_id_fkey
            FOREIGN KEY (parent_id) REFERENCES items(id) ON DELETE SET NULL;
    """)


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (
        SELECT 1 FROM upload_reservations WHERE parent_id IS NULL
    ) THEN RAISE EXCEPTION 'File lifecycle data exists; restore an approved backup';
    END IF; END $$;
        ALTER TABLE upload_reservations DROP CONSTRAINT upload_reservations_parent_id_fkey;
        ALTER TABLE upload_reservations ALTER COLUMN parent_id SET NOT NULL;
        ALTER TABLE upload_reservations ADD CONSTRAINT upload_reservations_parent_id_fkey
            FOREIGN KEY (parent_id) REFERENCES items(id) ON DELETE CASCADE;
    """)
