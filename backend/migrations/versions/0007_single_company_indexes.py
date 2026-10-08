"""Add the missing single-company query index for opportunity lookups.

Revision ID: 0007_single_company_indexes
Revises: 0006_integrity_controls
"""
import sqlalchemy as sa
from alembic import op

revision = '0007_single_company_indexes'
down_revision = '0006_integrity_controls'
branch_labels = None
depends_on = None


def upgrade():
    indexes = {item['name'] for item in sa.inspect(op.get_bind()).get_indexes('partner_opportunities')}
    if 'ix_partner_opportunities_customer_id' not in indexes:
        op.create_index(
            'ix_partner_opportunities_customer_id',
            'partner_opportunities',
            ['customer_id'],
        )


def downgrade():
    indexes = {item['name'] for item in sa.inspect(op.get_bind()).get_indexes('partner_opportunities')}
    if 'ix_partner_opportunities_customer_id' in indexes:
        op.drop_index('ix_partner_opportunities_customer_id', table_name='partner_opportunities')
