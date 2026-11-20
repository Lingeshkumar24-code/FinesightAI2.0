"""
Auth layer.
------------
This issues and verifies its own JWTs for local dev / the free-standing
version of this project. In production, swap `create_access_token` /
`decode_access_token` for verifying Supabase Auth's JWT against
Supabase's JWKS endpoint (Supabase issues the token on login/signup;
this API would only need to verify it, not mint its own) — the
`get_current_user` dependency is the one seam that changes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import Settings, get_settings

_bearer_scheme = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    sub: str  # user id
    business_id: str
    role: str = "owner"
    exp: int | None = None


def create_access_token(
    user_id: str, business_id: str, role: str, settings: Settings
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "business_id": business_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> TokenPayload:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return TokenPayload(**payload)
    except (JWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> TokenPayload:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token"
        )
    return decode_access_token(credentials.credentials, settings)
