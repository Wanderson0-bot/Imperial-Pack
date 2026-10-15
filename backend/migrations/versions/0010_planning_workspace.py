"""Add the planning workspace."""
from uuid import uuid4
from alembic import op
import sqlalchemy as sa

revision = '0010_planning_workspace'
down_revision = '0009_product_target_margin'
branch_labels = None
depends_on = None


def _create_index_if_missing(name: str, table_name: str, columns: list[str]):
    indexes = {item['name'] for item in sa.inspect(op.get_bind()).get_indexes(table_name)}
    if name not in indexes:
        op.create_index(name, table_name, columns)


def upgrade():
    if not sa.inspect(op.get_bind()).has_table('plannings'):
        op.create_table(
            'plannings',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('title', sa.String(180), nullable=False),
            sa.Column('description', sa.Text()),
            sa.Column('category', sa.String(30), nullable=False),
            sa.Column('expected_outcome', sa.Text()),
            sa.Column('start_date', sa.Date()),
            sa.Column('due_date', sa.Date()),
            sa.Column('status', sa.String(20), nullable=False, server_default='not_started'),
            sa.Column('priority', sa.String(12), nullable=False, server_default='medium'),
            sa.Column('observations', sa.Text()),
            sa.Column('archived_at', sa.DateTime(timezone=True)),
            sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL')),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
    _create_index_if_missing('ix_plannings_due_date', 'plannings', ['due_date'])
    _create_index_if_missing('ix_plannings_status', 'plannings', ['status'])
    _create_index_if_missing('ix_plannings_priority', 'plannings', ['priority'])
    _create_index_if_missing('ix_plannings_archived_at', 'plannings', ['archived_at'])
    _create_index_if_missing('ix_plannings_status_due', 'plannings', ['status', 'due_date'])

    if not sa.inspect(op.get_bind()).has_table('planning_tasks'):
        op.create_table(
            'planning_tasks',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('planning_id', sa.String(36), sa.ForeignKey('plannings.id', ondelete='CASCADE'), nullable=False),
            sa.Column('title', sa.String(180), nullable=False),
            sa.Column('description', sa.Text()),
            sa.Column('stage', sa.String(80)),
            sa.Column('status', sa.String(16), nullable=False, server_default='pending'),
            sa.Column('priority', sa.String(12), nullable=False, server_default='medium'),
            sa.Column('due_date', sa.Date()),
            sa.Column('assignee_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL')),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('observations', sa.Text()),
            sa.Column('completed_at', sa.DateTime(timezone=True)),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
    _create_index_if_missing('ix_planning_tasks_planning_id', 'planning_tasks', ['planning_id'])
    _create_index_if_missing('ix_planning_tasks_status', 'planning_tasks', ['status'])
    _create_index_if_missing('ix_planning_tasks_due_date', 'planning_tasks', ['due_date'])
    _create_index_if_missing('ix_planning_tasks_parent_order', 'planning_tasks', ['planning_id', 'sort_order'])

    if not sa.inspect(op.get_bind()).has_table('planning_goals'):
        op.create_table(
            'planning_goals',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('planning_id', sa.String(36), sa.ForeignKey('plannings.id', ondelete='SET NULL')),
            sa.Column('name', sa.String(180), nullable=False),
            sa.Column('description', sa.Text()),
            sa.Column('category', sa.String(30), nullable=False),
            sa.Column('initial_value', sa.Numeric(16, 4)),
            sa.Column('target_value', sa.Numeric(16, 4), nullable=False),
            sa.Column('current_value', sa.Numeric(16, 4), nullable=False, server_default='0'),
            sa.Column('unit', sa.String(40), nullable=False),
            sa.Column('start_date', sa.Date()),
            sa.Column('due_date', sa.Date()),
            sa.Column('status', sa.String(16), nullable=False, server_default='in_progress'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
    _create_index_if_missing('ix_planning_goals_planning_id', 'planning_goals', ['planning_id'])
    _create_index_if_missing('ix_planning_goals_due_date', 'planning_goals', ['due_date'])
    _create_index_if_missing('ix_planning_goals_status', 'planning_goals', ['status'])

    if not sa.inspect(op.get_bind()).has_table('planning_entity_links'):
        op.create_table(
            'planning_entity_links',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('planning_id', sa.String(36), sa.ForeignKey('plannings.id', ondelete='CASCADE'), nullable=False),
            sa.Column('customer_id', sa.String(36), sa.ForeignKey('customers.id', ondelete='CASCADE')),
            sa.Column('supplier_id', sa.String(36), sa.ForeignKey('suppliers.id', ondelete='CASCADE')),
            sa.Column('product_id', sa.String(36), sa.ForeignKey('products.id', ondelete='CASCADE')),
            sa.Column('purchase_id', sa.String(36), sa.ForeignKey('purchases.id', ondelete='CASCADE')),
            sa.Column('order_id', sa.String(36), sa.ForeignKey('orders.id', ondelete='CASCADE')),
            sa.Column('payable_id', sa.String(36), sa.ForeignKey('accounts_payable.id', ondelete='CASCADE')),
            sa.Column('receivable_id', sa.String(36), sa.ForeignKey('accounts_receivable.id', ondelete='CASCADE')),
            sa.CheckConstraint("(CASE WHEN customer_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN supplier_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN product_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN purchase_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN order_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN payable_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN receivable_id IS NOT NULL THEN 1 ELSE 0 END) = 1", name='planning_link_one_entity'),
        )
    _create_index_if_missing('ix_planning_entity_links_planning_id', 'planning_entity_links', ['planning_id'])

    if not sa.inspect(op.get_bind()).has_table('planning_opportunity_dismissals'):
        op.create_table(
            'planning_opportunity_dismissals',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('opportunity_key', sa.String(100), nullable=False, unique=True),
            sa.Column('product_id', sa.String(36), sa.ForeignKey('products.id', ondelete='CASCADE')),
            sa.Column('dismissed_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL')),
            sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=False),
        )

    bind = op.get_bind()
    permission = bind.execute(sa.text("SELECT id FROM permissions WHERE key = 'planning:manage'")).scalar_one_or_none()
    if permission is None:
        permission = str(uuid4())
        bind.execute(sa.text('INSERT INTO permissions (id, key, description) VALUES (:id, :key, :description)'), {
            'id': permission, 'key': 'planning:manage', 'description': 'Create and manage company planning',
        })
    bind.execute(sa.text("INSERT INTO role_permissions (role_id, permission_id) SELECT id, :permission_id FROM roles WHERE name = 'general_admin' AND NOT EXISTS (SELECT 1 FROM role_permissions WHERE role_id = roles.id AND permission_id = :permission_id)"), {'permission_id': permission})


def downgrade():
    op.drop_table('planning_opportunity_dismissals')
    op.drop_index('ix_planning_entity_links_planning_id', table_name='planning_entity_links')
    op.drop_table('planning_entity_links')
    op.drop_index('ix_planning_goals_status', table_name='planning_goals')
    op.drop_index('ix_planning_goals_due_date', table_name='planning_goals')
    op.drop_index('ix_planning_goals_planning_id', table_name='planning_goals')
    op.drop_table('planning_goals')
    op.drop_index('ix_planning_tasks_parent_order', table_name='planning_tasks')
    op.drop_index('ix_planning_tasks_due_date', table_name='planning_tasks')
    op.drop_index('ix_planning_tasks_status', table_name='planning_tasks')
    op.drop_index('ix_planning_tasks_planning_id', table_name='planning_tasks')
    op.drop_table('planning_tasks')
    op.drop_index('ix_plannings_status_due', table_name='plannings')
    op.drop_index('ix_plannings_archived_at', table_name='plannings')
    op.drop_index('ix_plannings_priority', table_name='plannings')
    op.drop_index('ix_plannings_status', table_name='plannings')
    op.drop_index('ix_plannings_due_date', table_name='plannings')
    op.drop_table('plannings')
