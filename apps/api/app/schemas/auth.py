import uuid

from pydantic import BaseModel, EmailStr, Field

from app.models.user import Role


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")


class UserRegister(BaseModel):
    organization_slug: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.VIEWER


class UserOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    email: EmailStr
    role: Role
    is_active: bool

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    organization_slug: str
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
