"""Initial relational schema for Imperial Pack.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
from app.database.base import Base
from app.database import models  # noqa: F401 - load metadata

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(bind=op.get_bind())


def downgrade():
    Base.metadata.drop_all(bind=op.get_bind())
