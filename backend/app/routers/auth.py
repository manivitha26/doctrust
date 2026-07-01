from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.models.user import UserCreate, UserPublic, Token, RefreshRequest
from app.services.auth_service import register_user, login_user, refresh_access_token, logout_user
from app.dependencies import get_current_user

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserPublic, status_code=201)
@limiter.limit("10/minute")
async def register(request: Request, user_in: UserCreate):
    """Create a new user account."""
    return await register_user(user_in)


@router.post("/token", response_model=Token)
@limiter.limit("5/minute")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate and receive access + refresh tokens."""
    return await login_user(form_data.username, form_data.password)


@router.post("/refresh", response_model=Token)
async def refresh(body: RefreshRequest):
    """Exchange a refresh token for a new token pair."""
    return await refresh_access_token(body.refresh_token)


@router.post("/logout", status_code=204)
async def logout(body: RefreshRequest, current_user: UserPublic = Depends(get_current_user)):
    """Revoke the refresh token (server-side logout)."""
    await logout_user(body.refresh_token)


@router.get("/me", response_model=UserPublic)
async def get_me(current_user: UserPublic = Depends(get_current_user)):
    """Return current authenticated user's profile."""
    return current_user
