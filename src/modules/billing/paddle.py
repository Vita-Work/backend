from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime


class PaddleWebhookVerificationError(ValueError):
    """Raised when a Paddle webhook cannot be authenticated."""


def parse_paddle_datetime(value: object) -> datetime | None:
    """Parse Paddle timestamps into timezone-aware datetimes."""
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def verify_paddle_webhook_signature(
    *,
    raw_body: bytes,
    signature_header: str | None,
    secret: str | None,
    now: datetime | None = None,
    tolerance_seconds: int = 300,
) -> None:
    """Validate a Paddle webhook signature using the raw request body."""
    if not secret:
        raise PaddleWebhookVerificationError("Paddle webhook secret is not configured.")
    if not signature_header:
        raise PaddleWebhookVerificationError("Missing Paddle-Signature header.")

    parts: dict[str, list[str]] = {}
    for item in signature_header.split(";"):
        key, _, value = item.partition("=")
        key = key.strip()
        value = value.strip()
        if not key or not value:
            continue
        parts.setdefault(key, []).append(value)

    timestamp_raw = next(iter(parts.get("ts", [])), None)
    signatures = parts.get("h1", [])
    if timestamp_raw is None or not signatures:
        raise PaddleWebhookVerificationError("Malformed Paddle-Signature header.")

    try:
        timestamp = int(timestamp_raw)
    except ValueError as exc:
        raise PaddleWebhookVerificationError("Invalid Paddle-Signature timestamp.") from exc

    current_time = now or datetime.now(UTC)
    if abs(current_time.timestamp() - timestamp) > tolerance_seconds:
        raise PaddleWebhookVerificationError("Paddle webhook timestamp is outside tolerance.")

    signed_payload = f"{timestamp}:{raw_body.decode('utf-8')}".encode()
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, signature) for signature in signatures):
        raise PaddleWebhookVerificationError("Invalid Paddle webhook signature.")
