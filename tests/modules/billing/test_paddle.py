from __future__ import annotations

import asyncio
import hashlib
import hmac
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from src.modules.billing import routes as billing_routes
from src.modules.billing.paddle import (
    PaddleWebhookVerificationError,
    verify_paddle_webhook_signature,
)


def test_verify_paddle_webhook_signature_accepts_valid_payload() -> None:
    raw_body = b'{"event_id":"evt_123"}'
    timestamp = "1774632000"
    secret = "whsec_test"
    expected = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}:{raw_body.decode('utf-8')}".encode(),
        hashlib.sha256,
    ).hexdigest()

    verify_paddle_webhook_signature(
        raw_body=raw_body,
        signature_header=f"ts={timestamp};h1={expected}",
        secret=secret,
        now=datetime.fromtimestamp(int(timestamp), tz=UTC),
        tolerance_seconds=5,
    )


def test_verify_paddle_webhook_signature_rejects_invalid_signature() -> None:
    with pytest.raises(PaddleWebhookVerificationError):
        verify_paddle_webhook_signature(
            raw_body=b'{"event_id":"evt_123"}',
            signature_header="ts=1774632000;h1=invalid",
            secret="whsec_test",
            now=datetime.fromtimestamp(1774632000, tz=UTC),
            tolerance_seconds=5,
        )


def test_sync_from_subscription_payload_upserts_local_subscription() -> None:
    created: list[SimpleNamespace] = []

    class FakeRepository:
        async def get_by_provider_subscription_id(self, *, provider_subscription_id: str):
            assert provider_subscription_id == "sub_123"
            return None

        async def get_by_provider_customer_id(self, *, provider_customer_id: str):
            assert provider_customer_id == "ctm_123"
            return None

        async def get_by_user_id(self, *, user_id: str):
            assert user_id == "user-1"
            return None

        def add(self, *, user_id: str):
            subscription = SimpleNamespace(
                user_id=user_id,
                provider="paddle",
                plan_code="pro",
                status=None,
                provider_customer_id=None,
                provider_subscription_id=None,
                provider_price_id=None,
                provider_transaction_id=None,
                current_period_starts_at=None,
                current_period_ends_at=None,
                next_billed_at=None,
                started_at=None,
                activated_at=None,
                canceled_at=None,
                scheduled_change_action=None,
                cancel_at_period_end=False,
                last_event_id=None,
                last_event_type=None,
                last_event_occurred_at=None,
                last_synced_at=None,
            )
            created.append(subscription)
            return subscription

    data = {
        "id": "sub_123",
        "customer_id": "ctm_123",
        "status": "active",
        "started_at": "2026-03-27T10:00:00Z",
        "next_billed_at": "2026-04-27T10:00:00Z",
        "custom_data": {"user_id": "user-1"},
        "current_billing_period": {
            "starts_at": "2026-03-27T10:00:00Z",
            "ends_at": "2026-04-27T10:00:00Z",
        },
        "items": [
            {
                "price": {
                    "id": "pri_123",
                }
            }
        ],
        "scheduled_change": {"action": "cancel"},
    }

    result_user_id = asyncio.run(
        billing_routes._sync_from_subscription_payload(
            repository=FakeRepository(),
            event_id="evt_123",
            event_type="subscription.updated",
            occurred_at=datetime(2026, 3, 27, 10, 5, tzinfo=UTC),
            data=data,
        )
    )

    assert result_user_id == "user-1"
    assert len(created) == 1
    subscription = created[0]
    assert subscription.status == "active"
    assert subscription.provider_customer_id == "ctm_123"
    assert subscription.provider_subscription_id == "sub_123"
    assert subscription.provider_price_id == "pri_123"
    assert subscription.cancel_at_period_end is True
