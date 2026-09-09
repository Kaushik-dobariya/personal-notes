from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_reset_token, hash_password, hash_reset_token, verify_password
from app.models.user import User
from app.repositories.reset_token_repo import PasswordResetTokenRepository
from app.repositories.user_repo import UserRepository
from app.schemas.user import PasswordChange, ResetPasswordRequest, UserCreate
from app.services.email_service import EmailServiceInterface, email_service


class AuthService:
    def __init__(self, session: AsyncSession, mailer: EmailServiceInterface = email_service):
        self.session = session
        self.user_repo = UserRepository(session)
        self.token_repo = PasswordResetTokenRepository(session)
        self.mailer = mailer

    async def register_user(self, data: UserCreate) -> User:
        """Register a new user, ensuring email uniqueness."""
        existing = await self.user_repo.get_by_email(data.email)
        if existing:
            raise ValueError("An account with this email address already exists.")

        hashed_pwd = hash_password(data.password)
        user = await self.user_repo.create(
            email=data.email,
            hashed_password=hashed_pwd,
            full_name=data.full_name
        )
        return user

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user by email and password."""
        user = await self.user_repo.get_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        return user

    async def change_password(self, user: User, data: PasswordChange) -> None:
        """Change password for an authenticated user."""
        if not verify_password(data.current_password, user.hashed_password):
            raise ValueError("Incorrect current password.")

        new_hashed = hash_password(data.new_password)
        await self.user_repo.update_password(user, new_hashed)

    async def request_password_reset(self, email: str, base_url: str) -> None:
        """
        Initiate password reset.
        Safe against user enumeration: always succeeds without disclosing account existence.
        """
        user = await self.user_repo.get_by_email(email)
        if not user or not user.is_active:
            # Silent return to prevent account enumeration attacks
            return

        # Invalidate any prior active tokens for this user
        await self.token_repo.invalidate_all_for_user(user.id)

        # Generate cryptographic token & SHA-256 hash
        raw_token, token_hash = generate_reset_token()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES)
        
        await self.token_repo.create_token(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at
        )

        reset_url = f"{base_url.rstrip('/')}/auth/reset-password?token={raw_token}"
        await self.mailer.send_password_reset(user.email, reset_url, user.full_name)

    async def reset_password(self, data: ResetPasswordRequest) -> None:
        """Verify reset token and update user password."""
        token_hash = hash_reset_token(data.token)
        reset_token = await self.token_repo.get_valid_token(token_hash)
        if not reset_token:
            raise ValueError("This password reset link is invalid or has expired.")

        user = await self.user_repo.get_by_id(reset_token.user_id)
        if not user or not user.is_active:
            raise ValueError("User account is inactive or not found.")

        new_hashed = hash_password(data.new_password)
        await self.user_repo.update_password(user, new_hashed)
        await self.token_repo.mark_as_used(reset_token)
