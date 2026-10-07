import uuid
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class CompanySignupRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=255)
    admin_full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: uuid.UUID
    company_id: Optional[uuid.UUID]
    full_name: str
    email: EmailStr
    role: str
    is_active: bool
    is_email_verified: bool

    class Config:
        from_attributes = True
