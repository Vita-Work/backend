# Billing and Subscriptions

## Product model

Vitable uses a simple two-tier entitlement model:

- `free`
  - manual search runs
  - only the top `billing_free_job_limit` jobs are visible
  - daily monitoring is disabled
- `pro`
  - full search results
  - daily monitoring is enabled

The backend is the source of truth for entitlements. The frontend may upsell or hide UI affordances, but access is enforced server-side.

## Paddle setup

Create and manage billing objects in Paddle:

1. Create product `Vitable Pro`
2. Create monthly recurring price `$20/month`
3. Create a client-side token for Paddle.js
4. Configure a webhook destination that points to `/billing/paddle/webhook`
5. Store only the resulting IDs/secrets in local environment variables

Required backend env vars:

- `PADDLE_ENVIRONMENT`
- `PADDLE_CLIENT_SIDE_TOKEN`
- `PADDLE_PRODUCT_ID_PRO`
- `PADDLE_PRICE_ID_PRO_MONTHLY`
- `PADDLE_WEBHOOK_SECRET`

Do not commit live or sandbox secrets to git.

## Request flow

### 1. Frontend loads billing state

`GET /me/billing`

The response contains:

- current entitlements
- current subscription snapshot, if any
- Paddle checkout config for the authenticated user

The frontend never embeds privileged Paddle credentials. It only receives the client-side token and public product/price IDs.

### 2. Frontend opens Paddle checkout

The frontend initializes Paddle.js in sandbox or production mode and opens checkout for the Pro monthly price.

Important runtime data:

- Paddle customer email or existing customer id
- `customData.user_id`

`customData.user_id` lets webhook processing map Paddle events back to the local user without brittle email-based matching.

### 3. Paddle sends webhooks

`POST /billing/paddle/webhook`

The webhook handler:

- verifies the Paddle signature
- stores the inbound event in `billing_webhook_events`
- processes it idempotently
- upserts the local `billing_subscriptions` row

This keeps the backend state authoritative even if the user closes the browser before the frontend refresh completes.

## Data model

### `billing_subscriptions`

One row per user. Stores the latest known Paddle subscription state plus monitoring preferences.

Key fields:

- provider ids
- status
- current billing period
- cancellation flags
- monitoring preferences

### `billing_webhook_events`

Stores inbound Paddle events for:

- idempotency
- replay/debug support
- operational visibility

## Search-result gating

Search result access is enforced in the search workflow itself:

- free users only receive the visible top slice
- hidden result counts are returned separately for upsell UI
- free users cannot run `monitoring_mode=true`
- when a user upgrades to `pro`, subsequent reads of `/me/search-jobs/runs/{id}` return the full visible set for that user

This means the free/pro split does not rely on frontend filtering.

## Frontend restore behavior

Subscriptions affect more than checkout UI, so the backend also drives recovery routes through `/me/app-state`.

Current mapping:

- extraction in progress -> `/onboarding/processing`
- onboarding clarification/confirmation -> `/onboarding/chat`
- search running -> `/searching`
- search ready -> `/results`

That route snapshot is what lets the frontend recover correctly after:

- refreshes
- reopening the app later
- completing checkout and polling for upgraded entitlements

## Tracker behavior after search

Search results and tracked jobs are deliberately separate concepts:

- search results live on the latest search workflow run
- tracker jobs are only the jobs the user explicitly saved

To avoid the product feeling empty right after a search, the frontend now falls back to the latest search results when the tracker is still empty. That keeps the experience understandable without changing the underlying data model.

## Daily monitoring

The ARQ billing cron runs hourly and checks for users whose monitoring window is due in their own timezone.

Current rules:

- only `pro` users are eligible
- monitoring runs once per local day
- default schedule is `09:00` in the user timezone
- the job reuses the latest completed onboarding profile

This keeps the scheduling logic simple while still supporting user-local delivery time.

## Local development

For local checkout testing:

- frontend can proxy API requests through the Vite dev server
- a public frontend tunnel can be approved in Paddle sandbox
- backend webhook can be exposed through a separate tunnel

This avoids putting backend secrets in the frontend and keeps the local flow close to production behavior.

## Security notes

- Entitlements are enforced server-side
- Paddle webhook signatures are verified
- Webhooks are processed idempotently
- Secrets stay in local env, never in committed source
- The client only receives Paddle public runtime configuration

## Why this stays simple

The design intentionally avoids a large billing abstraction layer.

We only store:

- one local subscription snapshot per user
- one webhook event log
- one cron job for monitoring eligibility

That is enough to support:

- free vs pro gating
- Paddle checkout
- webhook reconciliation
- daily monitoring

without adding premature complexity.
