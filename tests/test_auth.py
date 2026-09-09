import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.security import generate_reset_token, hash_reset_token
from app.repositories.reset_token_repo import PasswordResetTokenRepository
from tests.conftest import TestSessionLocal


@pytest.mark.asyncio
async def test_signup_and_login_flow(client: AsyncClient):
    # 1. Signup
    signup_data = {
        "full_name": "Alice Tester",
        "email": "alice@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!"
    }
    resp = await client.post("/auth/signup", data=signup_data, follow_redirects=False)
    assert resp.status_code == 303
    assert settings.COOKIE_NAME in resp.cookies

    # 2. Reject duplicate signup
    dup_resp = await client.post("/auth/signup", data=signup_data, follow_redirects=False)
    assert dup_resp.status_code == 400
    assert "already exists" in dup_resp.text

    # 3. Successful Login
    login_data = {
        "email": "alice@example.com",
        "password": "Password123!"
    }
    login_resp = await client.post("/auth/login", data=login_data, follow_redirects=False)
    assert login_resp.status_code == 303
    assert settings.COOKIE_NAME in login_resp.cookies

    # 4. Invalid Password Login
    bad_login = {
        "email": "alice@example.com",
        "password": "WrongPassword!"
    }
    bad_resp = await client.post("/auth/login", data=bad_login, follow_redirects=False)
    assert bad_resp.status_code == 400
    assert "Invalid email address or password" in bad_resp.text


@pytest.mark.asyncio
async def test_password_reset_flow(client: AsyncClient):
    # Request reset link
    forgot_resp = await client.post("/auth/forgot-password", data={"email": "alice@example.com"})
    assert forgot_resp.status_code == 200
    assert "receive password reset instructions" in forgot_resp.text

    # Fetch token from database directly
    async with TestSessionLocal() as session:
        from app.repositories.user_repo import UserRepository
        user_repo = UserRepository(session)
        user = await user_repo.get_by_email("alice@example.com")
        assert user is not None

        raw_token, token_hash = generate_reset_token()
        from datetime import datetime, timedelta, timezone
        token_repo = PasswordResetTokenRepository(session)
        await token_repo.create_token(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)
        )
        await session.commit()

    # Reset password with token
    reset_resp = await client.post(
        "/auth/reset-password",
        data={
            "token": raw_token,
            "new_password": "NewSecurePassword456!",
            "confirm_password": "NewSecurePassword456!"
        }
    )
    assert reset_resp.status_code == 200
    assert "successfully updated" in reset_resp.text

    # Login with new password
    new_login_resp = await client.post(
        "/auth/login",
        data={"email": "alice@example.com", "password": "NewSecurePassword456!"},
        follow_redirects=False
    )
    assert new_login_resp.status_code == 303
