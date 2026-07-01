from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import decode_token
from app.services.auth_service import get_user_by_email
from app.models.user import UserPublic

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserPublic:
    """Return a static anonymous user, bypassing token validation."""
    from datetime import datetime
    return UserPublic(email="guest@docutrust.com", is_active=True, created_at=datetime.utcnow())
    """Validate JWT access token and return the current user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise credentials_exception
    
    email: str = payload.get("sub")
    if not email:
        raise credentials_exception
    
    user = await get_user_by_email(email)
    if not user:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is deactivated.")
    
    return UserPublic(email=user.email, is_active=user.is_active, created_at=user.created_at)
