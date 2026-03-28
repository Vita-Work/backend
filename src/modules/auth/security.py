from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime

from pwdlib import PasswordHash

from src.config import get_settings

PASSWORD_HASHER = PasswordHash.recommended()


def utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return PASSWORD_HASHER.verify(password, password_hash)


def generate_otp_code(*, length: int) -> str:
    alphabet = "0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def _secret_bytes() -> bytes:
    return get_settings().auth_secret_key.encode("utf-8")


def _hash_scoped_value(*, scope: str, value: str) -> str:
    return hmac.new(_secret_bytes(), f"{scope}:{value}".encode(), hashlib.sha256).hexdigest()


def hash_otp_value(*, email: str, code: str) -> str:
    normalized = normalize_email(email)
    return _hash_scoped_value(scope="otp", value=f"{normalized}:{code}")


def hash_session_token(token: str) -> str:
    return _hash_scoped_value(scope="session", value=token)


def generate_resume_intake_token() -> str:
    return secrets.token_urlsafe(32)


def hash_resume_intake_token(token: str) -> str:
    return _hash_scoped_value(scope="resume-intake", value=token)
