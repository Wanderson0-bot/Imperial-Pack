from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    role_id: str
    is_active: bool = True
    is_general_admin: bool = False


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    role_id: str | None = None
    is_active: bool | None = None


class UserRecord(BaseModel):
    id: str
    name: str
    email: EmailStr
    role_id: str
    is_active: bool
    is_general_admin: bool

    model_config = {'from_attributes': True}


class RoleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str | None = None
    permissions: list[str] = []


class RoleRecord(BaseModel):
    id: str
    name: str
    description: str | None
    is_system: bool

    model_config = {'from_attributes': True}
