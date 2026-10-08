"""Extend existing partner signals for operational alerts and opportunities.

Revision ID: 0005_operational_signals
Revises: 5f9b0d56b0c6
"""
import sqlalchemy as sa
from alembic import op

revision = '0005_operational_signals'
down_revision = '5f9b0d56b0c6'
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    columns = {item['name'] for item in sa.inspect(op.get_bind()).get_columns(table_name)}
    if column.name not in columns:
        if op.get_bind().dialect.name == 'sqlite' and column.foreign_keys:
            with op.batch_alter_table(table_name) as batch:
                batch.add_column(column)
        else:
            op.add_column(table_name, column)


def _set_nullable(table_name: str, column_name: str, column_type: sa.types.TypeEngine, nullable: bool) -> None:
    column = next(item for item in sa.inspect(op.get_bind()).get_columns(table_name) if item['name'] == column_name)
    if column['nullable'] == nullable:
        return
    if op.get_bind().dialect.name == 'sqlite':
        with op.batch_alter_table(table_name) as batch:
            batch.alter_column(column_name, existing_type=column_type, nullable=nullable)
    else:
        op.alter_column(table_name, column_name, existing_type=column_type, nullable=nullable)


def _create_unique_index_if_missing(name: str, table_name: str, columns: list[str]) -> None:
    existing = {item['name'] for item in sa.inspect(op.get_bind()).get_indexes(table_name)}
    if name not in existing:
        op.create_index(name, table_name, columns, unique=True)


def upgrade():
    alert_columns = (
        sa.Column('entity_type', sa.String(30), nullable=False, server_default='partner'),
        sa.Column('entity_id', sa.String(36), nullable=True),
        sa.Column('entity_label', sa.String(180), nullable=False, server_default=''),
        sa.Column('title', sa.String(180), nullable=False, server_default=''),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('reason', sa.Text(), nullable=False, server_default=''),
        sa.Column('priority', sa.String(20), nullable=False, server_default='medium'),
        sa.Column('status', sa.String(20), nullable=False, server_default='OPEN'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('dedupe_key', sa.String(255), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=True),
    )
    opportunity_columns = (
        sa.Column('customer_id', sa.String(36), sa.ForeignKey('customers.id', ondelete='CASCADE', name='fk_partner_opportunities_customer_id'), nullable=True),
        sa.Column('entity_type', sa.String(30), nullable=False, server_default='partner'),
        sa.Column('entity_id', sa.String(36), nullable=True),
        sa.Column('entity_label', sa.String(180), nullable=False, server_default=''),
        sa.Column('title', sa.String(180), nullable=False, server_default=''),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('action', sa.Text(), nullable=False, server_default=''),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('dedupe_key', sa.String(255), nullable=True),
    )
    for column in alert_columns:
        _add_column_if_missing('partner_alerts', column)
    for column in opportunity_columns:
        _add_column_if_missing('partner_opportunities', column)

    op.execute(sa.text('UPDATE partner_alerts SET detected_at = created_at WHERE detected_at IS NULL'))
    _set_nullable('partner_alerts', 'detected_at', sa.DateTime(timezone=True), False)
    _set_nullable('partner_alerts', 'partner_id', sa.String(36), True)
    _set_nullable('partner_opportunities', 'partner_id', sa.String(36), True)
    _set_nullable('partner_opportunities', 'product_id', sa.String(36), True)
    _create_unique_index_if_missing('uq_partner_alerts_dedupe_key', 'partner_alerts', ['dedupe_key'])
    _create_unique_index_if_missing('uq_partner_opportunities_dedupe_key', 'partner_opportunities', ['dedupe_key'])


def downgrade():
    pass