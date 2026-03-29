from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.engine import get_db_session
from src.modules.auth.security import utcnow
from src.modules.billing.paddle import (
    PaddleWebhookVerificationError,
    parse_paddle_datetime,
    verify_paddle_webhook_signature,
)
from src.modules.billing.repository import (
    BillingAccessPassesRepository,
    BillingCreditLedgerRepository,
    BillingSubscriptionsRepository,
    BillingWebhookEventsRepository,
)
from src.modules.billing.schemas import PaddleWebhookResponse

router = APIRouter(prefix="/billing", tags=["billing"])
db_session_dependency = Depends(get_db_session)
settings = get_settings()


@router.post("/paddle/webhook", response_model=PaddleWebhookResponse)
async def paddle_webhook_route(
    request: Request,
    session: AsyncSession = db_session_dependency,
) -> PaddleWebhookResponse:
    raw_body = await request.body()
    try:
        verify_paddle_webhook_signature(
            raw_body=raw_body,
            signature_header=request.headers.get("Paddle-Signature"),
            secret=settings.paddle_webhook_secret,
            tolerance_seconds=settings.paddle_webhook_tolerance_seconds,
        )
    except PaddleWebhookVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    payload = await request.json()
    if not isinstance(payload, Mapping):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook payload."
        )

    event_id = str(payload.get("event_id") or "")
    event_type = str(payload.get("event_type") or "")
    occurred_at = parse_paddle_datetime(payload.get("occurred_at"))
    data = payload.get("data")
    if not event_id or not event_type or not isinstance(data, Mapping):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook payload."
        )

    subscription_repository = BillingSubscriptionsRepository(session=session)
    access_pass_repository = BillingAccessPassesRepository(session=session)
    credit_repository = BillingCreditLedgerRepository(session=session)
    event_repository = BillingWebhookEventsRepository(session=session)
    existing_event = await event_repository.get_by_provider_event_id(provider_event_id=event_id)
    if existing_event is not None and existing_event.status == "processed":
        return PaddleWebhookResponse()

    provider_subscription_id = _lookup_subscription_id(event_type=event_type, data=data)
    provider_customer_id = _lookup_customer_id(data)
    webhook_event = existing_event or event_repository.add(
        provider_event_id=event_id,
        event_type=event_type,
        payload=dict(payload),
        occurred_at=occurred_at,
        provider_customer_id=provider_customer_id,
        provider_subscription_id=provider_subscription_id,
    )

    try:
        user_id = await _sync_subscription_from_paddle_event(
            session=session,
            repository=subscription_repository,
            access_pass_repository=access_pass_repository,
            credit_repository=credit_repository,
            event_id=event_id,
            event_type=event_type,
            occurred_at=occurred_at,
            data=data,
        )
        webhook_event.status = "processed"
        webhook_event.user_id = user_id
        webhook_event.provider_customer_id = provider_customer_id
        webhook_event.provider_subscription_id = provider_subscription_id
        webhook_event.processed_at = utcnow()
        webhook_event.error_message = None
    except Exception as exc:
        webhook_event.status = "failed"
        webhook_event.error_message = str(exc)
        webhook_event.processed_at = utcnow()
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process Paddle webhook.",
        ) from exc

    await session.commit()
    return PaddleWebhookResponse()


async def _sync_subscription_from_paddle_event(
    *,
    session: AsyncSession,
    repository: BillingSubscriptionsRepository,
    access_pass_repository: BillingAccessPassesRepository,
    credit_repository: BillingCreditLedgerRepository,
    event_id: str,
    event_type: str,
    occurred_at,
    data: Mapping[str, object],
) -> str | None:
    if event_type.startswith("subscription."):
        return await _sync_from_subscription_payload(
            repository=repository,
            event_id=event_id,
            event_type=event_type,
            occurred_at=occurred_at,
            data=data,
        )
    if event_type.startswith("transaction."):
        return await _sync_from_transaction_payload(
            session=session,
            repository=repository,
            access_pass_repository=access_pass_repository,
            credit_repository=credit_repository,
            event_id=event_id,
            event_type=event_type,
            occurred_at=occurred_at,
            data=data,
        )
    return None


async def _sync_from_subscription_payload(
    *,
    repository: BillingSubscriptionsRepository,
    event_id: str,
    event_type: str,
    occurred_at,
    data: Mapping[str, object],
) -> str | None:
    provider_subscription_id = _lookup_subscription_id(event_type=event_type, data=data)
    provider_customer_id = _lookup_customer_id(data)
    user_id = _lookup_user_id(data)
    subscription = None
    if provider_subscription_id:
        subscription = await repository.get_by_provider_subscription_id(
            provider_subscription_id=provider_subscription_id
        )
    if subscription is None and provider_customer_id:
        subscription = await repository.get_by_provider_customer_id(
            provider_customer_id=provider_customer_id
        )
    if subscription is None and user_id:
        subscription = await repository.get_by_user_id(user_id=user_id)
    if subscription is None and user_id:
        subscription = repository.add(user_id=user_id)
    if subscription is None:
        return None

    items = data.get("items")
    price_id = None
    if isinstance(items, list) and items:
        first = items[0]
        if isinstance(first, Mapping):
            price = first.get("price")
            if isinstance(price, Mapping):
                price_id = _coerce_optional_str(price.get("id"))
            if price_id is None:
                price_id = _coerce_optional_str(first.get("price_id"))

    current_period = data.get("current_billing_period")
    current_period_starts_at = None
    current_period_ends_at = None
    if isinstance(current_period, Mapping):
        current_period_starts_at = parse_paddle_datetime(current_period.get("starts_at"))
        current_period_ends_at = parse_paddle_datetime(current_period.get("ends_at"))

    scheduled_change = data.get("scheduled_change")
    scheduled_change_action = None
    if isinstance(scheduled_change, Mapping):
        scheduled_change_action = _coerce_optional_str(scheduled_change.get("action"))

    subscription.provider = "paddle"
    subscription.plan_code = "pro"
    subscription.status = _coerce_optional_str(data.get("status")) or subscription.status
    subscription.provider_customer_id = provider_customer_id or subscription.provider_customer_id
    subscription.provider_subscription_id = (
        provider_subscription_id or subscription.provider_subscription_id
    )
    subscription.provider_price_id = price_id or subscription.provider_price_id
    subscription.current_period_starts_at = (
        current_period_starts_at or subscription.current_period_starts_at
    )
    subscription.current_period_ends_at = (
        current_period_ends_at or subscription.current_period_ends_at
    )
    subscription.next_billed_at = (
        parse_paddle_datetime(data.get("next_billed_at")) or subscription.next_billed_at
    )
    subscription.started_at = (
        parse_paddle_datetime(data.get("started_at")) or subscription.started_at
    )
    subscription.activated_at = (
        parse_paddle_datetime(data.get("first_billed_at"))
        or parse_paddle_datetime(data.get("started_at"))
        or subscription.activated_at
    )
    subscription.canceled_at = (
        parse_paddle_datetime(data.get("canceled_at")) or subscription.canceled_at
    )
    subscription.scheduled_change_action = scheduled_change_action
    subscription.cancel_at_period_end = scheduled_change_action == "cancel"
    subscription.last_event_id = event_id
    subscription.last_event_type = event_type
    subscription.last_event_occurred_at = occurred_at
    subscription.last_synced_at = utcnow()
    return subscription.user_id


async def _sync_from_transaction_payload(
    *,
    session: AsyncSession,
    repository: BillingSubscriptionsRepository,
    access_pass_repository: BillingAccessPassesRepository,
    credit_repository: BillingCreditLedgerRepository,
    event_id: str,
    event_type: str,
    occurred_at,
    data: Mapping[str, object],
) -> str | None:
    price_ids = _lookup_transaction_price_ids(data)
    provider_subscription_id = _coerce_optional_str(data.get("subscription_id"))
    provider_customer_id = _lookup_customer_id(data)
    user_id = _lookup_user_id(data)
    transaction_id = _coerce_optional_str(data.get("id"))
    transaction_status = _coerce_optional_str(data.get("status"))

    if (
        transaction_status == "completed"
        and user_id
        and _matches_any_price_id(
            price_ids,
            settings.paddle_price_id_weekly_sprint,
        )
    ):
        subscription = await repository.get_by_user_id(user_id=user_id)
        if subscription is None:
            subscription = repository.add(user_id=user_id)
        access_pass = None
        if transaction_id:
            access_pass = await access_pass_repository.get_by_provider_transaction_id(
                provider_transaction_id=transaction_id
            )
        starts_at = (
            parse_paddle_datetime(data.get("billed_at"))
            or parse_paddle_datetime(data.get("updated_at"))
            or occurred_at
            or utcnow()
        )
        ends_at = starts_at + timedelta(days=7)
        if access_pass is None:
            access_pass_repository.add(
                user_id=user_id,
                pass_type="weekly_sprint",
                provider="paddle",
                provider_transaction_id=transaction_id,
                provider_price_id=_first_matching_price_id(
                    price_ids,
                    settings.paddle_price_id_weekly_sprint,
                ),
                status="active",
                starts_at=starts_at,
                ends_at=ends_at,
            )
        else:
            access_pass.status = "active"
            access_pass.starts_at = starts_at
            access_pass.ends_at = ends_at
            access_pass.provider_price_id = (
                _first_matching_price_id(
                    price_ids,
                    settings.paddle_price_id_weekly_sprint,
                )
                or access_pass.provider_price_id
            )

    if (
        transaction_status == "completed"
        and user_id
        and _matches_any_price_id(
            price_ids,
            settings.paddle_price_id_tailor_pack_topup,
        )
    ):
        if transaction_id:
            existing_topup = await credit_repository.find_entry_by_meta_transaction_id(
                user_id=user_id,
                credit_type="job_pack",
                entry_type="topup_purchase",
                transaction_id=transaction_id,
            )
            if existing_topup is None:
                credit_repository.add_entry(
                    user_id=user_id,
                    credit_type="job_pack",
                    delta=settings.billing_tailor_pack_topup_credits,
                    entry_type="topup_purchase",
                    meta={
                        "transaction_id": transaction_id,
                        "price_id": _first_matching_price_id(
                            price_ids,
                            settings.paddle_price_id_tailor_pack_topup,
                        ),
                    },
                )
                await session.flush()

    subscription = None
    if provider_subscription_id:
        subscription = await repository.get_by_provider_subscription_id(
            provider_subscription_id=provider_subscription_id
        )
    if subscription is None and provider_customer_id:
        subscription = await repository.get_by_provider_customer_id(
            provider_customer_id=provider_customer_id
        )
    if subscription is None and user_id:
        subscription = await repository.get_by_user_id(user_id=user_id)
    if subscription is None and user_id and provider_subscription_id:
        subscription = repository.add(user_id=user_id)
    if subscription is None:
        return user_id

    subscription.provider = "paddle"
    subscription.plan_code = "pro"
    subscription.provider_customer_id = provider_customer_id or subscription.provider_customer_id
    subscription.provider_subscription_id = (
        provider_subscription_id or subscription.provider_subscription_id
    )
    subscription.provider_transaction_id = transaction_id
    matched_pro_price_id = _first_matching_price_id(
        price_ids,
        settings.paddle_price_id_pro_search_monthly,
        settings.paddle_price_id_pro_monthly,
    )
    subscription.provider_price_id = matched_pro_price_id or subscription.provider_price_id
    if transaction_status == "completed" and subscription.status in {None, "inactive", "canceled"}:
        subscription.status = "active"
    subscription.last_event_id = event_id
    subscription.last_event_type = event_type
    subscription.last_event_occurred_at = occurred_at
    subscription.last_synced_at = utcnow()
    return subscription.user_id


def _lookup_user_id(data: Mapping[str, object]) -> str | None:
    custom_data = data.get("custom_data")
    if isinstance(custom_data, Mapping):
        return _coerce_optional_str(custom_data.get("user_id"))
    return None


def _lookup_subscription_id(*, event_type: str, data: Mapping[str, object]) -> str | None:
    if event_type.startswith("subscription."):
        return _coerce_optional_str(data.get("id"))
    return _coerce_optional_str(data.get("subscription_id"))


def _lookup_customer_id(data: Mapping[str, object]) -> str | None:
    direct_customer_id = _coerce_optional_str(data.get("customer_id"))
    if direct_customer_id:
        return direct_customer_id
    customer = data.get("customer")
    if isinstance(customer, Mapping):
        return _coerce_optional_str(customer.get("id"))
    return None


def _lookup_transaction_price_ids(data: Mapping[str, object]) -> list[str]:
    items = data.get("items")
    if not isinstance(items, list):
        return []

    price_ids: list[str] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        price_id = _coerce_optional_str(item.get("price_id"))
        if price_id:
            price_ids.append(price_id)
        price = item.get("price")
        if isinstance(price, Mapping):
            nested_price_id = _coerce_optional_str(price.get("id"))
            if nested_price_id:
                price_ids.append(nested_price_id)
    return list(dict.fromkeys(price_ids))


def _matches_any_price_id(price_ids: list[str], *candidates: str | None) -> bool:
    candidate_set = {candidate for candidate in candidates if candidate}
    return any(price_id in candidate_set for price_id in price_ids)


def _first_matching_price_id(price_ids: list[str], *candidates: str | None) -> str | None:
    candidate_set = {candidate for candidate in candidates if candidate}
    for price_id in price_ids:
        if price_id in candidate_set:
            return price_id
    return None


def _coerce_optional_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
