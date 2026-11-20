"""
Auth routes.

This is a minimal, self-contained demo login so the whole stack runs
without an external auth provider configured. It issues this API's own
JWT for a single hardcoded demo business/user.

Production note: swap this for Supabase Auth. The frontend would call
Supabase's `signInWithPassword` directly (never this endpoint), and this
API would stop minting tokens altogether — `get_current_user` in
app/core/security.py would instead verify the Supabase-issued JWT
against Supabase's JWKS. Nothing else in the API changes.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.core.security import TokenPayload, create_access_token, get_current_user
from app.models.schemas import LoginRequest, LoginResponse, MeResponse
from app.db.tenant import demo_business_id

router = APIRouter(prefix="/auth", tags=["auth"])

_DEMO_BUSINESS_ID = demo_business_id()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, settings: Settings = Depends(get_settings)) -> LoginResponse:
    if not payload.email or not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing credentials")

    if settings.ENV == "production" and not settings.ALLOW_DEMO_AUTH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo authentication is disabled; configure Supabase Auth.",
        )

    # Demo-only check. Replace with Supabase Auth in production.
    token = create_access_token(
        user_id=payload.email, business_id=_DEMO_BUSINESS_ID, role="owner", settings=settings
    )
    return LoginResponse(access_token=token, business_id=_DEMO_BUSINESS_ID)


@router.get("/me", response_model=MeResponse)
def me(current_user: TokenPayload = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        user_id=current_user.sub, business_id=current_user.business_id, role=current_user.role
    )
