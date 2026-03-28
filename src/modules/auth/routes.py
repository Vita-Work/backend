from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.engine import get_db_session
from src.extensions.resend import ResendClient, ResendEmailError
from src.logger import get_logger
from src.modules.auth.dependencies import (
    AuthContext,
    clear_auth_cookie,
    get_current_auth_context_optional,
    set_auth_cookie,
)
from src.modules.auth.repository import AuthRepository
from src.modules.auth.schemas import (
    AdminLoginRequest,
    AuthSessionResponse,
    AuthSessionUserResponse,
    GenericAcceptedResponse,
    LogoutResponse,
    RequestEmailCodeRequest,
    VerifyEmailCodeRequest,
)
from src.modules.auth.security import (
    generate_otp_code,
    generate_session_token,
    hash_otp_value,
    hash_session_token,
    normalize_email,
    utcnow,
    verify_password,
)
from src.modules.me.frontend_state import build_app_state_snapshot
from src.modules.users.repository import UsersRepository

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger("auth.routes")
settings = get_settings()
db_session_dependency = Depends(get_db_session)
optional_auth_context_dependency = Depends(get_current_auth_context_optional)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _client_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _generic_accepted() -> GenericAcceptedResponse:
    return GenericAcceptedResponse(
        detail="If the email is allowed, a verification code has been sent."
    )


async def _session_response(
    *,
    context: AuthContext | None,
    session: AsyncSession | None = None,
    is_new_user: bool | None = None,
) -> AuthSessionResponse:
    if context is None:
        return AuthSessionResponse(authenticated=False)
    metadata: dict[str, object | None] = {}
    if context.role == "user" and session is not None:
        snapshot = await build_app_state_snapshot(session=session, user=context.user)
        metadata = {
            "is_new_user": is_new_user if is_new_user is not None else snapshot.is_new_user,
            "next_route": snapshot.next_route,
            "needs_onboarding": snapshot.needs_onboarding,
            "has_active_onboarding_session": snapshot.has_active_onboarding_session,
            "has_completed_onboarding": snapshot.has_completed_onboarding,
            "has_search_results": snapshot.has_search_results,
            "has_tracker_jobs": snapshot.has_tracker_jobs,
        }
    return AuthSessionResponse(
        authenticated=True,
        role=context.role,
        user=AuthSessionUserResponse.model_validate(context.user),
        **metadata,
    )


@router.post(
    "/email/request-code",
    response_model=GenericAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_email_code_route(
    payload: RequestEmailCodeRequest,
    request: Request,
    session: AsyncSession = db_session_dependency,
) -> GenericAcceptedResponse:
    email = normalize_email(payload.email)
    auth_repository = AuthRepository(session=session)
    now = utcnow()

    recent_request_count = await auth_repository.count_recent_challenges(
        email=email,
        since=now - timedelta(hours=1),
    )
    if recent_request_count >= settings.auth_email_requests_per_hour:
        logger.info("challenge_rate_limited", email=email)
        return _generic_accepted()

    latest_challenge = await auth_repository.get_latest_challenge(email=email)
    if latest_challenge is not None and latest_challenge.last_sent_at >= (
        now - timedelta(seconds=settings.auth_email_resend_cooldown_seconds)
    ):
        logger.info("challenge_cooldown_active", email=email)
        return _generic_accepted()

    code = generate_otp_code(length=settings.auth_email_otp_length)
    code_hash = hash_otp_value(email=email, code=code)
    await auth_repository.invalidate_active_challenges(email=email)
    challenge = auth_repository.add_challenge(
        email=email,
        code_hash=code_hash,
        expires_at=now + timedelta(minutes=settings.auth_email_otp_ttl_minutes),
        max_attempts=settings.auth_email_otp_max_attempts,
        last_sent_at=now,
        request_ip=_client_ip(request),
        user_agent=_client_user_agent(request),
    )
    await session.commit()
    logger.info("challenge_created", email=email)

    resend = ResendClient()
    verification_url = f"{settings.app_base_url.rstrip('/')}/verify?email={email}"
    html = (
        f"<p>Your Vita sign-in code is <strong>{code}</strong>.</p>"
        f"<p>It expires in {settings.auth_email_otp_ttl_minutes} minutes.</p>"
        f"<p>You can enter it in the app, or continue at "
        f'<a href="{verification_url}">{verification_url}</a>.</p>'
    )
    text = (
        f"Your Vita sign-in code is {code}. "
        f"It expires in {settings.auth_email_otp_ttl_minutes} minutes. "
        f"Open {verification_url} to continue."
    )
    try:
        await resend.send_email(
            to_email=email,
            subject="Your Vita sign-in code",
            html=html,
            text=text,
        )
    except ResendEmailError as exc:
        # Avoid leaving a persisted cooldown/OTP behind when the email never left the system.
        await session.delete(challenge)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return _generic_accepted()


@router.post("/email/verify-code", response_model=AuthSessionResponse)
async def verify_email_code_route(
    payload: VerifyEmailCodeRequest,
    request: Request,
    response: Response,
    session: AsyncSession = db_session_dependency,
) -> AuthSessionResponse:
    email = normalize_email(payload.email)
    auth_repository = AuthRepository(session=session)
    users_repository = UsersRepository(session=session)
    now = utcnow()

    challenge = await auth_repository.get_active_challenge_for_verification(email=email, now=now)
    if challenge is None:
        logger.info("verify_failed_no_active_challenge", email=email)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code."
        )

    if challenge.attempt_count >= challenge.max_attempts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Code is no longer valid."
        )

    challenge.attempt_count += 1
    if challenge.code_hash != hash_otp_value(email=email, code=payload.code.strip()):
        await session.commit()
        logger.info(
            "verify_failed_invalid_code", email=email, attempt_count=challenge.attempt_count
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code."
        )

    challenge.consumed_at = now
    user = await users_repository.get_by_email(email=email)
    is_new_user = user is None
    if user is None:
        user = users_repository.add(
            email=email,
            full_name=payload.full_name.strip() if payload.full_name else None,
            timezone=(payload.timezone.strip() or "UTC"),
            locale=payload.locale.strip() if payload.locale else None,
            role="user",
            password_hash=None,
            email_verified_at=now,
            status="active",
        )
        await session.flush()
    else:
        if user.status != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled.")
        if user.role != "user":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Use admin login for this account."
            )
        if user.email_verified_at is None:
            user.email_verified_at = now
        if payload.full_name and not user.full_name:
            user.full_name = payload.full_name.strip()
        if payload.locale and not user.locale:
            user.locale = payload.locale.strip()
        if payload.timezone and user.timezone == "UTC":
            user.timezone = payload.timezone.strip() or "UTC"

    raw_session_token = generate_session_token()
    auth_repository.add_session(
        session_token_hash=hash_session_token(raw_session_token),
        user_id=str(user.id),
        role_snapshot="user",
        expires_at=now + timedelta(days=settings.auth_session_ttl_days),
        created_ip=_client_ip(request),
        user_agent=_client_user_agent(request),
    )
    await session.commit()
    await session.refresh(user)
    set_auth_cookie(response=response, role="user", token=raw_session_token)
    logger.info("verify_succeeded", email=email, user_id=user.id)
    return await _session_response(
        context=AuthContext(
            user=user,
            session_id="bootstrap-login",
            role="user",
            cookie_name=settings.auth_cookie_name_user,
        ),
        session=session,
        is_new_user=is_new_user,
    )


@router.post("/admin/login", response_model=AuthSessionResponse)
async def admin_login_route(
    payload: AdminLoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = db_session_dependency,
) -> AuthSessionResponse:
    users_repository = UsersRepository(session=session)
    auth_repository = AuthRepository(session=session)
    email = normalize_email(payload.email)
    user = await users_repository.get_by_email(email=email)
    if user is None or user.role != "admin" or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled.")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    now = utcnow()
    raw_session_token = generate_session_token()
    auth_repository.add_session(
        session_token_hash=hash_session_token(raw_session_token),
        user_id=str(user.id),
        role_snapshot="admin",
        expires_at=now + timedelta(days=settings.auth_session_ttl_days),
        created_ip=_client_ip(request),
        user_agent=_client_user_agent(request),
    )
    await session.commit()
    set_auth_cookie(response=response, role="admin", token=raw_session_token)
    return await _session_response(
        context=AuthContext(
            user=user,
            session_id="bootstrap-login",
            role="admin",
            cookie_name=settings.auth_cookie_name_admin,
        ),
        session=session,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout_route(
    request: Request,
    response: Response,
    context: AuthContext | None = optional_auth_context_dependency,
    session: AsyncSession = db_session_dependency,
) -> LogoutResponse:
    if context is not None:
        auth_repository = AuthRepository(session=session)
        request_cookie_value = request.cookies.get(context.cookie_name)
        if request_cookie_value:
            await auth_repository.revoke_session_by_hash(
                session_token_hash=hash_session_token(request_cookie_value),
                now=utcnow(),
            )
            await session.commit()
    clear_auth_cookie(response=response)
    return LogoutResponse(detail="Logged out.")


@router.get("/session", response_model=AuthSessionResponse)
async def get_auth_session_route(
    context: AuthContext | None = optional_auth_context_dependency,
    session: AsyncSession = db_session_dependency,
) -> AuthSessionResponse:
    return await _session_response(context=context, session=session)
