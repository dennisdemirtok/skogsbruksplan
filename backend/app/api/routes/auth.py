import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "owner"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    role: str
    organization: Optional[str] = None
    createdAt: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            name=user.full_name,
            role=user.role,
            organization=str(user.organization_id) if user.organization_id else None,
            createdAt=user.created_at,
        )


class TokenResponse(BaseModel):
    accessToken: str
    tokenType: str = "bearer"
    user: UserResponse


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == request.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="En användare med denna e-postadress finns redan",
        )

    user = User(
        id=uuid.uuid4(),
        email=request.email,
        hashed_password=get_password_hash(request.password),
        full_name=request.name,
        role=request.role,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()

    access_token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(
        accessToken=access_token,
        user=UserResponse.from_user(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Felaktig e-postadress eller lösenord",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(
        accessToken=access_token,
        user=UserResponse.from_user(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.from_user(current_user)
