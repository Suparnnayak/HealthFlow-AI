import os
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session

from app.auth.schemas import UserCreate, UserLogin, UserResponse, TokenResponse, RefreshTokenRequest
from app.auth.service import (
    create_user,
    authenticate_user,
    get_user_hospital_ids,
    issue_refresh_token,
    verify_and_rotate_refresh_token,
    revoke_refresh_token,
)
from app.auth.security import create_access_token
from app.core.config import get_settings
from database.session import get_db


router = APIRouter(prefix="/auth", tags=["auth"])

# CORS origins — driven by env var, no hardcoded localhost
_ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001",
).split(",")


def _cors_response(request: Request) -> Response:
    """Create CORS response for preflight requests."""
    origin = request.headers.get("origin", "")
    allow_origin = origin if origin in _ALLOWED_ORIGINS else _ALLOWED_ORIGINS[0]

    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": allow_origin,
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, HEAD, PATCH",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "3600",
        },
    )


@router.options("/register")
async def options_register(request: Request):
    return _cors_response(request)


@router.options("/login")
async def options_login(request: Request):
    return _cors_response(request)


@router.options("/refresh")
async def options_refresh(request: Request):
    return _cors_response(request)


@router.options("/logout")
async def options_logout(request: Request):
    return _cors_response(request)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)) -> TokenResponse:
    """Register a new user and return JWT access token + refresh token."""
    user = create_user(db, user_in)
    hospital_ids = get_user_hospital_ids(db, user)

    settings = get_settings()
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "hospital_ids": hospital_ids,
        },
        expires_delta=access_token_expires,
    )
    refresh_token = issue_refresh_token(db, user.id)

    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        hospital_ids=hospital_ids,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=user_resp,
    )


@router.post("/login", response_model=TokenResponse)
def login(user_in: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate user and return access token with role/hospital_ids claims + refresh token."""
    user = authenticate_user(db, user_in.email, user_in.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    hospital_ids = get_user_hospital_ids(db, user)

    settings = get_settings()
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "hospital_ids": hospital_ids,
        },
        expires_delta=access_token_expires,
    )
    refresh_token = issue_refresh_token(db, user.id)

    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        hospital_ids=hospital_ids,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=user_resp,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(body: RefreshTokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Rotate refresh token and issue new short-lived access token."""
    user, new_refresh_token = verify_and_rotate_refresh_token(db, body.refresh_token)
    hospital_ids = get_user_hospital_ids(db, user)

    settings = get_settings()
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "hospital_ids": hospital_ids,
        },
        expires_delta=access_token_expires,
    )

    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        hospital_ids=hospital_ids,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        user=user_resp,
    )


@router.post("/logout")
def logout_endpoint(body: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Revoke refresh token on logout."""
    revoked = revoke_refresh_token(db, body.refresh_token)
    return {"status": "success", "revoked": revoked}



