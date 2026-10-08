import getpass
import sys
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth.security import hash_password
from app.database.models import Permission, Role, RolePermission, User
from app.database.session import get_engine, set_auth_lookup_context, set_bootstrap_context, set_user_context

PERMISSIONS = {
    'users:read': 'View internal users', 'users:create': 'Create internal users', 'users:manage': 'Update users and roles', 'users:manage_roles': 'Create roles and delegate permissions',
    'customers:read': 'View customers', 'customers:create': 'Create customers', 'customers:update': 'Update customers',
    'products:read': 'View products', 'products:create': 'Create products', 'products:update': 'Update products',
    'suppliers:read': 'View suppliers', 'suppliers:manage': 'Manage suppliers',
    'purchases:read': 'View purchases', 'purchases:create': 'Register purchases', 'purchases:cancel': 'Cancel and reverse purchases',
    'orders:read': 'View orders', 'orders:create': 'Create orders', 'orders:update_status': 'Change order status',
    'inventory:read': 'View inventory', 'inventory:adjust': 'Adjust inventory',
    'pricing:read': 'View pricing reviews', 'pricing:approve': 'Approve prices',
    'partners:read': 'View Imperial Partners', 'partners:activate': 'Activate Imperial Partners', 'partners:deactivate': 'Deactivate Imperial Partners', 'partners:conditions': 'Manage partner cycles and conditions', 'partners:evaluate_predictions': 'Evaluate prediction outcomes',
    'finance:read': 'View financial records', 'finance:write': 'Manage financial records',
    'alerts:manage': 'Resolve and ignore operational alerts', 'opportunities:manage': 'Update operational opportunities',
    'intelligence:read': 'View intelligence status', 'intelligence:train': 'Train and activate validated intelligence models', 'reports:read': 'View reports',
}


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit('Usage: python -m app.auth.bootstrap admin1@example.com admin2@example.com')
    emails = [value.strip().lower() for value in sys.argv[1:]]
    if emails[0] == emails[1]:
        raise SystemExit('The two administrator emails must be different.')
    passwords = [getpass.getpass(f'Password for {email} (minimum 12 characters): ') for email in emails]
    if any(len(password) < 12 for password in passwords):
        raise SystemExit('Administrator passwords must contain at least 12 characters.')
    engine = get_engine()
    with Session(engine) as db:
        set_auth_lookup_context(db, True)
        set_bootstrap_context(db, True)
        if db.scalar(select(User.id).limit(1)):
            raise SystemExit('Bootstrap only runs on an empty users table.')
        set_user_context(db, 'bootstrap', True)
        set_auth_lookup_context(db, False)
        set_bootstrap_context(db, False)
        admin_role = Role(name='general_admin', description='Sócio administrador geral', is_system=True)
        db.add(admin_role)
        permissions = [Permission(key=key, description=description) for key, description in PERMISSIONS.items()]
        db.add_all(permissions)
        db.flush()
        db.add_all(RolePermission(role_id=admin_role.id, permission_id=permission.id) for permission in permissions)
        users = [User(name=email.split('@')[0], email=email, password_hash=hash_password(password), role_id=admin_role.id, is_general_admin=True, is_active=True) for email, password in zip(emails, passwords)]
        db.add_all(users)
        db.commit()
    print('Two general administrators created.')


if __name__ == '__main__':
    main()
