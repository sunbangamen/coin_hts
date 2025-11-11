"""Create backtest_results table for Task 3.5

Revision ID: 001
Revises:
Create Date: 2025-11-11

This migration creates the PostgreSQL table for storing backtest result metadata
along with necessary indexes, constraints, and triggers.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create backtest_results table and supporting objects"""

    # Create backtest_results table
    op.create_table(
        'backtest_results',
        sa.Column('task_id', sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('strategy', sa.VARCHAR(100), nullable=False),
        sa.Column('symbols', sa.JSON(), nullable=False),  # JSONB
        sa.Column('start_date', sa.DATE(), nullable=False),
        sa.Column('end_date', sa.DATE(), nullable=False),
        sa.Column('timeframe', sa.VARCHAR(10), nullable=True),
        sa.Column('status', sa.VARCHAR(20), nullable=False),
        sa.Column('parquet_path', sa.VARCHAR(500), nullable=False, unique=True),
        sa.Column('file_size', sa.BIGINT(), nullable=True),
        sa.Column('record_count', sa.INTEGER(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),

        # Constraints
        sa.CheckConstraint("status IN ('completed', 'failed', 'running')", name='status_valid'),
        sa.CheckConstraint('start_date <= end_date', name='date_order'),
    )

    # Create indexes
    op.create_index('idx_backtest_results_created_at', 'backtest_results', ['created_at'], postgresql_using='btree')
    op.create_index('idx_backtest_results_strategy', 'backtest_results', ['strategy'], postgresql_using='btree')
    op.create_index('idx_backtest_results_status', 'backtest_results', ['status'], postgresql_using='btree')
    op.create_index('idx_backtest_results_task_id', 'backtest_results', ['task_id'], postgresql_using='btree')

    # Create JSONB index for symbols
    op.execute(
        "CREATE INDEX idx_backtest_results_symbols ON backtest_results USING GIN (symbols)"
    )

    # Create trigger function for updated_at
    op.execute("""
    CREATE OR REPLACE FUNCTION update_backtest_results_timestamp()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    # Create trigger
    op.execute("""
    CREATE TRIGGER backtest_results_update_timestamp
    BEFORE UPDATE ON backtest_results
    FOR EACH ROW
    EXECUTE FUNCTION update_backtest_results_timestamp();
    """)


def downgrade() -> None:
    """Drop backtest_results table and supporting objects"""

    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS backtest_results_update_timestamp ON backtest_results")

    # Drop trigger function
    op.execute("DROP FUNCTION IF EXISTS update_backtest_results_timestamp()")

    # Drop indexes (cascade)
    op.drop_index('idx_backtest_results_symbols', table_name='backtest_results')
    op.drop_index('idx_backtest_results_task_id', table_name='backtest_results')
    op.drop_index('idx_backtest_results_status', table_name='backtest_results')
    op.drop_index('idx_backtest_results_strategy', table_name='backtest_results')
    op.drop_index('idx_backtest_results_created_at', table_name='backtest_results')

    # Drop table
    op.drop_table('backtest_results')
