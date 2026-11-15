"""Add external identities for Google OIDC providers."""
from alembic import op
import sqlalchemy as sa

revision = "0002_external_identities"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_identities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_subject", sa.String(255), nullable=False),
        sa.Column("email_at_link", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_external_identity_provider_subject"),
    )
    op.create_index("ix_external_identities_account_id", "external_identities", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_external_identities_account_id", table_name="external_identities")
    op.drop_table("external_identities")

