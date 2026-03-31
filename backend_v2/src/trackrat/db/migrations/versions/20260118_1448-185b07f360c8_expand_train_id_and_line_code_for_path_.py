"""expand train_id and line_code for PATH support

Revision ID: 185b07f360c8
Revises: b7c8d9e0f1a2
Create Date: 2026-01-18 14:48:55.619081

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "185b07f360c8"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Expand train_id and line_code columns to support PATH train data."""
    # PATH train IDs are ~21 characters (e.g., PATH_859_2a76b1f269dc)
    op.alter_column(
        "train_journeys",
        "train_id",
        type_=sa.String(30),
        existing_type=sa.String(10),
        existing_nullable=False,
    )

    # PATH line codes are ~6 characters (e.g., HOB-33)
    op.alter_column(
        "train_journeys",
        "line_code",
        type_=sa.String(10),
        existing_type=sa.String(2),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Revert column sizes (may cause data truncation if PATH data exists)."""
    op.alter_column(
        "train_journeys",
        "train_id",
        type_=sa.String(10),
        existing_type=sa.String(30),
        existing_nullable=False,
    )

    op.alter_column(
        "train_journeys",
        "line_code",
        type_=sa.String(2),
        existing_type=sa.String(10),
        existing_nullable=False,
    )
