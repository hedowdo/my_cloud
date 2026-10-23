"""Durable bounded authentication rate buckets and security activity actions."""

from alembic import op

revision = "0002_identity"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None

BASE_ACTIONS = """'upload','download','rename','move','folder_create','replace','trash',
'restore','permanent_delete','icon_update','invitation_create','invitation_revoke',
'user_deactivate'"""
SECURITY_ACTIONS = "'bootstrap','user_register','login','logout','session_revoke'"


def upgrade() -> None:
    op.execute("""CREATE TABLE auth_rate_limits (
        key_hash bytea PRIMARY KEY CHECK (octet_length(key_hash)=32),
        attempts integer NOT NULL CHECK (attempts BETWEEN 1 AND 1001),
        expires_at timestamptz NOT NULL
    ); CREATE INDEX auth_rate_expiry_idx ON auth_rate_limits(expires_at);""")
    op.execute("ALTER TABLE activity DROP CONSTRAINT activity_action_check")
    op.execute(
        f"ALTER TABLE activity ADD CONSTRAINT activity_action_check "
        f"CHECK (action IN ({BASE_ACTIONS},{SECURITY_ACTIONS}))"
    )


def downgrade() -> None:
    # Refuse to erase/reinterpret security history during rollback of a populated database.
    op.execute(f"""DO $$ BEGIN IF EXISTS (
        SELECT 1 FROM activity WHERE action IN ({SECURITY_ACTIONS})
    ) THEN RAISE EXCEPTION 'Security history exists; use the approved backup recovery plan';
    END IF; END $$;""")
    op.execute("ALTER TABLE activity DROP CONSTRAINT activity_action_check")
    op.execute(
        f"ALTER TABLE activity ADD CONSTRAINT activity_action_check "
        f"CHECK (action IN ({BASE_ACTIONS}))"
    )
    op.execute("DROP TABLE auth_rate_limits")
