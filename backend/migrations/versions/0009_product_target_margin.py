"""Add a per-product target margin."""
from alembic import op
import sqlalchemy as sa

revision = '0009_product_target_margin'
down_revision = '0008_intelligence_training_permission'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('products', sa.Column('target_margin_percent', sa.Numeric(8, 4), nullable=False, server_default='30'))


def downgrade():
    op.drop_column('products', 'target_margin_percent')
