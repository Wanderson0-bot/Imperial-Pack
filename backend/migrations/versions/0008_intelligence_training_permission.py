"""Add the existing RBAC permission needed to train intelligence models.

Revision ID: 0008_intelligence_training_permission
Revises: 0007_single_company_indexes
"""
from alembic import op
import sqlalchemy as sa

revision = '0008_intelligence_training_permission'
down_revision = '0007_single_company_indexes'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    permissions = sa.table('permissions', sa.column('id', sa.String()), sa.column('key', sa.String()), sa.column('description', sa.String()))
    roles = sa.table('roles', sa.column('id', sa.String()), sa.column('name', sa.String()))
    role_permissions = sa.table('role_permissions', sa.column('role_id', sa.String()), sa.column('permission_id', sa.String()))
    permission_id = bind.execute(sa.select(permissions.c.id).where(permissions.c.key == 'intelligence:train')).scalar_one_or_none()
    if permission_id is None:
        import uuid
        permission_id = str(uuid.uuid4())
        bind.execute(permissions.insert().values(id=permission_id, key='intelligence:train', description='Train and activate validated intelligence models'))
    admin_role_id = bind.execute(sa.select(roles.c.id).where(roles.c.name == 'general_admin')).scalar_one_or_none()
    if admin_role_id is not None:
        assigned = bind.execute(sa.select(role_permissions.c.role_id).where(role_permissions.c.role_id == admin_role_id, role_permissions.c.permission_id == permission_id)).first()
        if assigned is None:
            bind.execute(role_permissions.insert().values(role_id=admin_role_id, permission_id=permission_id))


def downgrade():
    # Preserve RBAC grants and audit history if this permission was used.
    pass
