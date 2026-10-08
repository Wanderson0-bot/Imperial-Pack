"""Allow customer addresses to be partially provided.

Revision ID: 0004_optional_customer_address
Revises: 0003_commercial_links, cee76fea1373
"""
import sqlalchemy as sa
from alembic import op

revision = '0004_optional_customer_address'
down_revision = ('0003_commercial_links', 'cee76fea1373')
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column['name']: column for column in sa.inspect(bind).get_columns('customer_addresses')}
    street_required = not columns['street']['nullable']
    city_required = not columns['city']['nullable']
    if not street_required and not city_required:
        return
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table('customer_addresses') as batch:
            if street_required:
                batch.alter_column('street', existing_type=sa.String(length=200), nullable=True)
            if city_required:
                batch.alter_column('city', existing_type=sa.String(length=120), nullable=True)
        return
    if street_required:
        op.alter_column('customer_addresses', 'street', existing_type=sa.String(length=200), nullable=True)
    if city_required:
        op.alter_column('customer_addresses', 'city', existing_type=sa.String(length=120), nullable=True)


def downgrade():
    pass