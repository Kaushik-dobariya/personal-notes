from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class EmailServiceInterface(ABC):
    """Abstract interface for application mail operations."""

    @abstractmethod
    async def send_password_reset(self, to_email: str, reset_url: str, user_name: str) -> None:
        """Send password reset instructions to user."""
        pass


class ConsoleEmailService(EmailServiceInterface):
    """
    Development email service that logs formatted reset emails to console.
    Ensures safe local testing without requiring external SMTP configuration.
    """

    async def send_password_reset(self, to_email: str, reset_url: str, user_name: str) -> None:
        border = "=" * 70
        print(f"\n{border}")
        print(f"📧 [DEV EMAIL SERVICE] PASSWORD RESET REQUEST")
        print(f"To: {user_name} <{to_email}>")
        print(f"Subject: Reset Your Personal Notes Password")
        print(f"-" * 70)
        print(f"Hello {user_name},")
        print(f"A password reset request was received for your account.")
        print(f"Click the link below to set a new password:")
        print(f"\n👉 {reset_url}\n")
        print(f"This link is valid for 30 minutes. If you did not request this, please ignore.")
        print(f"{border}\n")
        logger.info(f"Password reset link generated for {to_email}")


# Default singleton instance for the app
email_service: EmailServiceInterface = ConsoleEmailService()
