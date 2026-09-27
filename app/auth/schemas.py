from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    name: Optional[str] = Field(None, description="Display name")


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="Plaintext password")
    role: Optional[str] = Field("hospital_staff", description="User role: admin | hospital_staff")
    hospital_ids: Optional[List[str]] = Field(None, description="Assigned hospital CCNs for hospital_staff")


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: UUID
    role: str
    is_active: bool
    hospital_ids: List[str] = Field(default_factory=list, description="Allowed hospital CCNs")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token")



