"""Durable retirement of explicitly removed/superseded custom icons."""

from alembic import op

revision = "0005_media_cleanup"
down_revision = "0004_transfer_parents"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE media_cleanup (
        blob_id uuid PRIMARY KEY REFERENCES blobs(id) ON DELETE CASCADE,
        created_at timestamptz NOT NULL DEFAULT now()
    ); GRANT SELECT,INSERT,UPDATE,DELETE ON media_cleanup TO cloud_app;""")


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM media_cleanup)
        OR EXISTS (SELECT 1 FROM items WHERE icon_blob_id IS NOT NULL)
        OR EXISTS (SELECT 1 FROM upload_reservations WHERE parent_id IS NULL)
        THEN RAISE EXCEPTION 'File lifecycle data exists; restore an approved backup';
        END IF; END $$; DROP TABLE media_cleanup;""")
