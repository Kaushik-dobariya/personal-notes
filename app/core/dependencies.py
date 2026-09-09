from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repo import UserRepository


class AuthenticationRequiredException(Exception):
    """Raised when an unauthenticated request attempts to access a protected page or HTMX fragment."""
    pass


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Retrieve current user from session cookie if present and valid."""
    token = request.cookies.get(settings.COOKIE_NAME)
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    user_id_str = payload.get("sub")
    if not user_id_str:
        return None

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        return None

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user or not user.is_active:
        return None

    return user


async def get_current_user(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional)
) -> User:
    """Enforce authentication. Redirects browsers to login or triggers HTMX client redirect."""
    if not current_user:
        raise AuthenticationRequiredException()
    return current_user
