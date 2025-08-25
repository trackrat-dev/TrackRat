"""Add cached API responses table

Revision ID: 89bfc05ebfac
Revises: 11dc95145b34
Create Date: 2025-08-25 13:28:17.034024

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '89bfc05ebfac'
down_revision = '11dc95145b34'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    # Create cached_api_responses table for pre-computed API responses
    op.create_table(
        'cached_api_responses',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('endpoint', sa.String(100), nullable=False),
        sa.Column('params_hash', sa.String(64), nullable=False),
        sa.Column('params', sa.JSON, nullable=False),
        sa.Column('response', sa.JSON, nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # Add indexes for efficient lookup and cleanup
    op.create_index('idx_cached_api_endpoint_params', 'cached_api_responses', ['endpoint', 'params_hash'])
    op.create_index('idx_cached_api_expires', 'cached_api_responses', ['expires_at'])
    
    # Add unique constraint to prevent duplicates
    op.create_unique_constraint('uq_cached_api_endpoint_params', 'cached_api_responses', ['endpoint', 'params_hash'])


def downgrade() -> None:
    """Revert migration."""
    op.drop_table('cached_api_responses')