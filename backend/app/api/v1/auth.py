"""Auth: register, login, refresh, logout, JWT."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import security
from app.core.rate_limit import limiter
from app.core.redis_client import revoke_token
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token_payload,
    get_password_hash,
    verify_password,
)
from app.db.session import get_async_session
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RefreshRequest, Token, UserLogin, UserRegister

router = APIRouter()


def _token_response(user_id):
    return Token(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/register")
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: UserRegister,
    session: AsyncSession = Depends(get_async_session),
) -> Token:
    existing = await UserRepository.get_by_email(session, body.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    user = await UserRepository.create(session, body.email, get_password_hash(body.password))
    await session.commit()
    return _token_response(user.id)


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: UserLogin,
    session: AsyncSession = Depends(get_async_session),
) -> Token:
    user = await UserRepository.get_by_email(session, body.email)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return _token_response(user.id)


@router.post("/refresh")
@limiter.limit("20/minute")
async def refresh(
    request: Request,
    body: RefreshRequest,
    session: AsyncSession = Depends(get_async_session),
) -> Token:
    payload = decode_access_token_payload(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    try:
        user_id = UUID(sub)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = await UserRepository.get_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return _token_response(user.id)


@router.post("/logout")
@limiter.limit("30/minute")
async def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """Revoke the current access token (Bearer). No body required."""
    if not credentials:
        return {"detail": "No token to revoke"}
    payload = decode_access_token_payload(credentials.credentials)
    if payload and payload.get("jti") and payload.get("type") == "access":
        await revoke_token(payload["jti"])
    return {"detail": "Logged out"}
