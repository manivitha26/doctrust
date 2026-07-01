from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, status

from app.database import users_collection, refresh_tokens_collection
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.user import UserCreate, UserInDB, UserPublic, Token
from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def get_user_by_email(email: str) -> Optional[UserInDB]:
    user_data = await users_collection.find_one({"email": email})
    if user_data:
        user_data["id"] = str(user_data.get("_id", ""))
        return UserInDB(**user_data)
    return None


async def register_user(user_in: UserCreate) -> UserPublic:
    existing = await get_user_by_email(user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists."
        )
    
    user_doc = {
        "email": user_in.email,
        "hashed_password": get_password_hash(user_in.password),
        "is_active": True,
        "created_at": datetime.utcnow(),
    }
    result = await users_collection.insert_one(user_doc)
    logger.info("user_registered", email=user_in.email, user_id=str(result.inserted_id))
    
    return UserPublic(email=user_in.email, created_at=user_doc["created_at"])


async def authenticate_user(email: str, password: str) -> Optional[UserInDB]:
    user = await get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def login_user(email: str, password: str) -> Token:
    user = await authenticate_user(email, password)
    if not user:
        logger.warning("login_failed", email=email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is deactivated.")
    
    access_token = create_access_token(subject=user.email)
    refresh_token = create_refresh_token(subject=user.email)
    
    # Store refresh token in DB for invalidation capability
    await refresh_tokens_collection.insert_one({
        "token": refresh_token,
        "user_email": user.email,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    })
    
    logger.info("user_logged_in", email=user.email)
    return Token(access_token=access_token, refresh_token=refresh_token)


async def refresh_access_token(refresh_token: str) -> Token:
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token."
        )
    
    # Check it exists in DB (not revoked)
    stored = await refresh_tokens_collection.find_one({"token": refresh_token})
    if not stored:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked."
        )
    
    email = payload["sub"]
    # Rotate: delete old, issue new
    await refresh_tokens_collection.delete_one({"token": refresh_token})
    
    new_access = create_access_token(subject=email)
    new_refresh = create_refresh_token(subject=email)
    
    await refresh_tokens_collection.insert_one({
        "token": new_refresh,
        "user_email": email,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    })
    
    logger.info("token_refreshed", email=email)
    return Token(access_token=new_access, refresh_token=new_refresh)


async def logout_user(refresh_token: str):
    """Revoke refresh token from DB."""
    await refresh_tokens_collection.delete_one({"token": refresh_token})
    logger.info("user_logged_out")
