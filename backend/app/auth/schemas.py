from pydantic import BaseModel, EmailStr, Field


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class InitialRegistrationInput(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


class TokenOutput(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    expires_in: int


class UserOutput(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    permissions: list[str]
    is_general_admin: bool = False

    model_config = {'from_attributes': True}
