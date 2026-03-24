from __future__ import annotations

import httpx

from src.config import get_settings
from src.logger import get_logger

logger = get_logger("extensions.resend")


class ResendEmailError(RuntimeError):
    """Raised when an email cannot be sent through Resend."""


class ResendClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def send_email(
        self,
        *,
        to_email: str,
        subject: str,
        html: str,
        text: str,
    ) -> None:
        if not self.settings.resend_api_key or not self.settings.resend_from_email:
            raise ResendEmailError("Resend is not configured.")

        payload: dict[str, object] = {
            "from": self.settings.resend_from_email,
            "to": [to_email],
            "subject": subject,
            "html": html,
            "text": text,
        }
        if self.settings.resend_reply_to:
            payload["reply_to"] = self.settings.resend_reply_to

        logger.info("email_send_requested", provider="resend", to_email=to_email)
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if response.status_code >= 400:
            logger.error(
                "email_send_failed",
                provider="resend",
                to_email=to_email,
                status_code=response.status_code,
                response=response.text,
            )
            raise ResendEmailError("Failed to send email.")

        logger.info("email_send_succeeded", provider="resend", to_email=to_email)
