"""Create Account Server authentication schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("accounts", sa.Column("id", sa.String(36), primary_key=True), sa.Column("email", sa.String(320), nullable=False), sa.Column("email_normalized", sa.String(320), nullable=False), sa.Column("password_hash", sa.Text(), nullable=False), sa.Column("email_verified_at", sa.DateTime(timezone=True)), sa.Column("status", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_login_at", sa.DateTime(timezone=True)), sa.UniqueConstraint("email_normalized", name="uq_accounts_email_normalized"))
    op.create_table("devices", sa.Column("id", sa.String(36), primary_key=True), sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False), sa.Column("device_name", sa.String(120), nullable=False), sa.Column("platform", sa.String(32), nullable=False), sa.Column("client_version", sa.String(64)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.create_index("ix_devices_account_id", "devices", ["account_id"])
    op.create_table("sessions", sa.Column("id", sa.String(36), primary_key=True), sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False), sa.Column("device_id", sa.String(36), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False), sa.Column("access_token_hash", sa.String(64), nullable=False), sa.Column("refresh_token_hash", sa.String(64), nullable=False), sa.Column("token_family_id", sa.String(36), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)), sa.Column("replaced_by_session_id", sa.String(36)))
    op.create_index("ix_sessions_refresh_token_hash", "sessions", ["refresh_token_hash"])
    op.create_index("ix_sessions_access_token_hash", "sessions", ["access_token_hash"])
    op.create_index("ix_sessions_account_id", "sessions", ["account_id"])
    for table, index in (("email_verification_tokens", "ix_email_verification_token_hash"), ("password_reset_tokens", "ix_password_reset_token_hash")):
        op.create_table(table, sa.Column("id", sa.String(36), primary_key=True), sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False), sa.Column("token_hash", sa.String(64), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("consumed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
        op.create_index(index, table, ["token_hash"])
    op.create_table("security_events", sa.Column("id", sa.String(36), primary_key=True), sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id", ondelete="SET NULL")), sa.Column("event_type", sa.String(64), nullable=False), sa.Column("safe_metadata", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_security_events_account_created", "security_events", ["account_id", "created_at"])


def downgrade() -> None:
    op.drop_table("security_events")
    op.drop_table("password_reset_tokens")
    op.drop_table("email_verification_tokens")
    op.drop_table("sessions")
    op.drop_table("devices")
    op.drop_table("accounts")

