from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_db_session
from src.modules.auth.dependencies import AuthContext, require_authenticated_user
from src.modules.billing.repository import (
    BillingAccessPassesRepository,
    BillingCreditLedgerRepository,
    BillingSubscriptionsRepository,
)
from src.modules.billing.schemas import BillingOverviewResponse, BillingPreferencesUpdateRequest
from src.modules.billing.service import (
    build_billing_entitlements,
    build_billing_overview,
    ensure_job_pack_allowances,
)

router = APIRouter(prefix="/me/billing", tags=["billing"])
user_auth_dependency = Depends(require_authenticated_user)
db_session_dependency = Depends(get_db_session)


@router.get("", response_model=BillingOverviewResponse)
async def get_my_billing_route(
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> BillingOverviewResponse:
    user_id = str(context.user.id)
    subscription_repository = BillingSubscriptionsRepository(session=session)
    access_pass_repository = BillingAccessPassesRepository(session=session)
    credit_repository = BillingCreditLedgerRepository(session=session)

    subscription = await subscription_repository.get_by_user_id(user_id=user_id)
    access_pass = await access_pass_repository.get_active_for_user(user_id=user_id)
    remaining_job_pack_credits = await ensure_job_pack_allowances(
        user_id=user_id,
        subscription=subscription,
        access_pass=access_pass,
        credit_repository=credit_repository,
    )
    await session.commit()

    return build_billing_overview(
        subscription=subscription,
        access_pass=access_pass,
        remaining_job_pack_credits=remaining_job_pack_credits,
        timezone=context.user.timezone,
    )


@router.patch("/preferences", response_model=BillingOverviewResponse)
async def update_my_billing_preferences_route(
    payload: BillingPreferencesUpdateRequest,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> BillingOverviewResponse:
    user_id = str(context.user.id)
    subscription_repository = BillingSubscriptionsRepository(session=session)
    access_pass_repository = BillingAccessPassesRepository(session=session)
    credit_repository = BillingCreditLedgerRepository(session=session)

    subscription = await subscription_repository.get_by_user_id(user_id=user_id)
    access_pass = await access_pass_repository.get_active_for_user(user_id=user_id)
    entitlements = build_billing_entitlements(subscription=subscription, access_pass=access_pass)
    if not entitlements.can_use_daily_monitoring:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Daily monitoring is available on Vitable Pro.",
        )

    if subscription is None:
        subscription = subscription_repository.add(user_id=user_id)
        subscription.plan_code = access_pass.pass_type if access_pass is not None else "pro"
        subscription.status = "inactive"
        if access_pass is not None:
            subscription.provider = access_pass.provider
            subscription.provider_transaction_id = access_pass.provider_transaction_id
            subscription.provider_price_id = access_pass.provider_price_id
            subscription.started_at = access_pass.starts_at
        await session.flush()

    if payload.monitoring_enabled is not None:
        subscription.monitoring_enabled = payload.monitoring_enabled
    if payload.monitoring_hour_local is not None:
        subscription.monitoring_hour_local = payload.monitoring_hour_local
        subscription.monitoring_minute_local = 0
    await session.commit()
    await session.refresh(subscription)
    remaining_job_pack_credits = await ensure_job_pack_allowances(
        user_id=user_id,
        subscription=subscription,
        access_pass=access_pass,
        credit_repository=credit_repository,
    )
    await session.commit()
    return build_billing_overview(
        subscription=subscription,
        access_pass=access_pass,
        remaining_job_pack_credits=remaining_job_pack_credits,
        timezone=context.user.timezone,
    )
