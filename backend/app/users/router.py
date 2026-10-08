from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.auth.dependencies import current_user, require_permission
from app.auth.security import hash_password
from app.core.audit import audit
from app.database.models import Permission, Role, RolePermission, User
from app.database.session import get_db
from app.users.schemas import RoleCreate, RoleRecord, UserCreate, UserRecord, UserUpdate

router = APIRouter(prefix='/users', tags=['users'])


@router.get('/roles', response_model=list[RoleRecord])
def list_roles(_: User = Depends(require_permission('users:read')), db: Session = Depends(get_db)):
    return list(db.scalars(select(Role).order_by(Role.name)))


@router.post('/roles', response_model=RoleRecord, status_code=status.HTTP_201_CREATED)
def create_role(payload: RoleCreate, actor: User = Depends(require_permission('users:manage_roles')), db: Session = Depends(get_db)):
    if db.scalar(select(Role.id).where(Role.name == payload.name)):
        raise HTTPException(status_code=409, detail='Role already exists.')
    permissions = list(db.scalars(select(Permission).where(Permission.key.in_(payload.permissions)))) if payload.permissions else []
    if len(permissions) != len(set(payload.permissions)):
        raise HTTPException(status_code=422, detail='One or more permissions are invalid.')
    role = Role(name=payload.name, description=payload.description)
    db.add(role)
    db.flush()
    db.add_all(RolePermission(role_id=role.id, permission_id=permission.id) for permission in permissions)
    audit(db, actor.id, 'users.role.create', 'role', role.id, {'permissions': payload.permissions})
    db.commit()
    db.refresh(role)
    return role


@router.get('', response_model=list[UserRecord])
def list_users(_: User = Depends(require_permission('users:read')), db: Session = Depends(get_db)):
    rows = db.scalars(select(User).order_by(User.name))
    return [UserRecord(id=user.id, name=user.name, email=user.email, role_id=user.role_id, is_active=user.is_active, is_general_admin=user.is_general_admin) for user in rows]


@router.post('', response_model=UserRecord, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, actor: User = Depends(require_permission('users:create')), db: Session = Depends(get_db)):
    if payload.is_general_admin and not actor.is_general_admin:
        raise HTTPException(status_code=403, detail='Only a general administrator can create another general administrator.')
    if db.scalar(select(User.id).where(User.email == str(payload.email).lower())):
        raise HTTPException(status_code=409, detail='Email is already in use.')
    role = db.get(Role, payload.role_id)
    if not role:
        raise HTTPException(status_code=422, detail='Unknown role.')
    user = User(name=payload.name, email=str(payload.email).lower(), password_hash=hash_password(payload.password), role_id=role.id, is_active=payload.is_active, is_general_admin=payload.is_general_admin)
    db.add(user)
    db.flush()
    audit(db, actor.id, 'users.create', 'user', user.id, {'email': user.email, 'role_id': user.role_id, 'is_active': user.is_active, 'is_general_admin': user.is_general_admin})
    db.commit()
    db.refresh(user)
    return UserRecord(id=user.id, name=user.name, email=user.email, role_id=user.role_id, is_active=user.is_active, is_general_admin=user.is_general_admin)


@router.patch('/{user_id}', response_model=UserRecord)
def update_user(user_id: str, payload: UserUpdate, actor: User = Depends(require_permission('users:manage')), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found.')
    changes = payload.model_dump(exclude_unset=True)
    previous = {'role_id': user.role_id, 'is_active': user.is_active}
    if 'role_id' in changes:
        role = db.get(Role, changes['role_id'])
        if not role:
            raise HTTPException(status_code=422, detail='Unknown role.')
        user.role_id = role.id
    if 'is_active' in changes:
        user.is_active = changes['is_active']
    audit(db, actor.id, 'users.update', 'user', user.id, {'before': previous, 'after': {'role_id': user.role_id, 'is_active': user.is_active}})
    db.commit()
    db.refresh(user)
    return UserRecord(id=user.id, name=user.name, email=user.email, role_id=user.role_id, is_active=user.is_active, is_general_admin=user.is_general_admin)


@router.delete('/{user_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str, actor: User = Depends(current_user), db: Session = Depends(get_db)):
    if not actor.is_general_admin:
        raise HTTPException(status_code=403, detail='Only a general administrator can remove users.')
    if user_id == actor.id:
        raise HTTPException(status_code=409, detail='A general administrator cannot remove their own account.')
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found.')
    if user.is_general_admin:
        general_admin_count = db.scalar(select(func.count(User.id)).where(User.is_general_admin.is_(True))) or 0
        if general_admin_count <= 1:
            raise HTTPException(status_code=409, detail='The last general administrator cannot be removed.')

    audit(db, actor.id, 'users.delete', 'user', user.id, {
        'email': user.email,
        'role_id': user.role_id,
        'is_general_admin': user.is_general_admin,
    })
    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
