from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_db_session
from src.modules.auth.dependencies import AuthContext, require_authenticated_user
from src.modules.billing.repository import BillingSubscriptionsRepository
from src.modules.billing.schemas import BillingOverviewResponse, BillingPreferencesUpdateRequest
from src.modules.billing.service import build_billing_entitlements, build_billing_overview

router = APIRouter(prefix="/me/billing", tags=["billing"])
user_auth_dependency = Depends(require_authenticated_user)
db_session_dependency = Depends(get_db_session)


@router.get("", response_model=BillingOverviewResponse)
async def get_my_billing_route(
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> BillingOverviewResponse:
    subscription = await BillingSubscriptionsRepository(session=session).get_by_user_id(
        user_id=str(context.user.id)
    )
    return build_billing_overview(subscription=subscription, timezone=context.user.timezone)


@router.patch("/preferences", response_model=BillingOverviewResponse)
async def update_my_billing_preferences_route(
    payload: BillingPreferencesUpdateRequest,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> BillingOverviewResponse:
    repository = BillingSubscriptionsRepository(session=session)
    subscription = await repository.get_by_user_id(user_id=str(context.user.id))
    entitlements = build_billing_entitlements(subscription=subscription)
    if subscription is None or not entitlements.can_use_daily_monitoring:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Daily monitoring is available on Vitable Pro.",
        )

    if payload.monitoring_enabled is not None:
        subscription.monitoring_enabled = payload.monitoring_enabled
    if payload.monitoring_hour_local is not None:
        subscription.monitoring_hour_local = payload.monitoring_hour_local
        subscription.monitoring_minute_local = 0
    await session.commit()
    await session.refresh(subscription)
    return build_billing_overview(subscription=subscription, timezone=context.user.timezone)
