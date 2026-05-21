# backend/app/schemas/auth_schemas.py

from pydantic import BaseModel, EmailStr, field_validator ,Field
from typing import Optional
from uuid import UUID
from datetime import datetime
from app.core.enums import UserRole


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)  
    name: str
    country: Optional[str] = "PK"

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    role: UserRole    
    tenant_id: str


class UserResponse(BaseModel):
    id: UUID
    email: str                                                                                                                                                                                                                                                                                
    role: UserRole     
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)   
    role: UserRole

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v