# SaaS Template API Reference

> Plain markdown: load this file into any LLM or coding tool when integrating.
> Human-readable docs: https://your-domain.com/docs
> Create API keys: https://your-domain.com/api-keys (sign-in required)

**Base URL:** `https://your-domain.com/api`
**Auth:** `Authorization: Bearer sk_live_<64 hex chars>`
**Content-Type:** `application/json` (for POST bodies)
**Errors:** RFC 9457 `application/problem+json`

---

## Quick start

1. Sign in at https://your-domain.com and open **API Keys**.
2. Create a key (name only). Copy the `sk_live_…` value — it is shown once.
3. Note your organization id (`org_id`) from the dashboard URL or org settings.
4. Call org endpoints with the key:

```bash
curl -sS "https://your-domain.com/api/orgs/$ORG_ID/credits" \
  -H "Authorization: Bearer sk_live_YOUR_KEY"
```

---

## Authentication

### API keys (programmatic)

| Header | Value |
|--------|--------|
| `Authorization` | `Bearer sk_live_…` |

- Keys are **org-scoped**. The `{org_id}` in the path must match the key's organization.
- Keys authenticate as **member** level: they can read the wallet, ledger, and usage endpoints below. The AI endpoints (LLM completions, generations) additionally require a **session JWT** — they are dashboard flows in the template. When you add your own metered endpoints, accept `CurrentMember` (works with keys) and pass `actor.api_key_id` into `CreditEngine.reserve` so usage is attributed to the key.
- Keys **cannot** create/revoke keys, manage billing, or change members (use a browser session for those).
- Prefix format: `sk_live_` + 64 hex characters. Only the prefix is shown after creation; the full secret is shown once.
- Revoked keys return `401`.

### Session JWT (dashboard / admin)

Browser sessions use a short-lived JWT (`Bearer <jwt>`). Same org-scoped paths. Prefer API keys for server-to-server integrations.

### Managing keys (JWT only)

| Method | Path | Role |
|--------|------|------|
| `POST` | `/orgs/{org_id}/api-keys` | Admin |
| `GET` | `/orgs/{org_id}/api-keys` | Member |
| `DELETE` | `/orgs/{org_id}/api-keys/{key_id}` | Admin |

Create body:

```json
{
  "name": "Production"
}
```

Create response includes `raw_key` (once) plus metadata (`id`, `name`, `key_prefix`, `created_at`).

---

## Credits

Metered actions hold credits from the org wallet up front, then capture on a delivered result / release on failure — you are never charged for errors.

| Action | Credits | Endpoints |
|--------|---------|-----------|
| LLM call | 1 | `POST …/llm/complete` |
| Image (Nano Banana / GPT) | 5 | `POST …/generations` |
| Video (VEO) | 50 | `POST …/generations` |

Costs come from `GET /credits/actions` (public). Insufficient balance → problem+json credit error. Buy packs in the dashboard.

### Wallet & usage (Member)

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/orgs/{org_id}/credits` | Balance, monthly allowance, pending holds |
| `GET` | `/orgs/{org_id}/credits/history` | Ledger (`limit`, `offset`) |
| `GET` | `/orgs/{org_id}/credits/usage` | Per-member/API-key spend for a period (`period=YYYY-MM`) |

---

## Rate limits

Per-IP (SlowAPI). Exceeding returns `429`.

| Endpoint | Limit |
|----------|-------|
| LLM complete | 60/minute |
| Create generation | 20/minute |

---

## Endpoints

### Text completion (LLM)

```
POST /orgs/{org_id}/llm/complete        (session JWT only — 202 Accepted)
```

```json
{
  "provider": "gemini",        // "gemini" | "openai" | "anthropic"
  "prompt": "Summarize …",
  "max_tokens": 1024
}
```

The call is accepted, credits are held, and the completion runs in a worker. Poll:

```
GET /orgs/{org_id}/llm/calls             — recent calls (limit, offset)
GET /orgs/{org_id}/llm/calls/{call_id}   — one call (status: pending | succeeded | failed)
```

Succeeded calls include `response_text`, `tokens_in`, `tokens_out`, `credits_cost`.

### Generations (image / video)

```
POST /orgs/{org_id}/generations          (session JWT — 202 Accepted)
```

```json
{
  "kind": "image_nano_banana",  // "image_nano_banana" | "image_gpt" | "video_veo"
  "prompt": "A lighthouse at dusk"
}
```

```
GET    /orgs/{org_id}/generations                        — list (limit, offset)
GET    /orgs/{org_id}/generations/{generation_id}        — poll status
GET    /orgs/{org_id}/generations/{generation_id}/file   — download the result
POST   /orgs/{org_id}/generations/{generation_id}/cancel — cancel a pending job (credits released)
DELETE /orgs/{org_id}/generations/{generation_id}        — delete a finished generation
```

Two-phase credit flow: creating the job holds credits; the worker captures them when the asset is delivered or releases them if the provider fails.

### Blog (public, no auth)

```
GET /blog/posts                — published posts, newest first (page, page_size ≤ 50, q=search, tag=filter)
GET /blog/posts/{slug}         — one published post (markdown in `content`, plus author_name, tags, related[])
GET /blog/tags                 — published tags with counts
GET /blog/rss.xml              — RSS 2.0 feed (latest 20)
GET /blog/sitemap.xml          — sitemap of marketing pages + published posts
```

Draft, scheduled, and archived posts return 404. Authoring (including scheduled
publishing and AI draft generation) is superuser-only via the admin console (`/admin/blog`).

---

## Errors

All errors are RFC 9457 `application/problem+json`:

```json
{
  "type": "about:blank",
  "title": "Not enough credits",
  "status": 402,
  "detail": "…",
  "code": "ERR_CRD_001",
  "instance": "err_…"
}
```

- `code` is a stable machine-readable identifier — branch on it, never on `detail` text.
- `instance` is a correlation reference; include it in support requests.
- Retryable errors carry a `retry` hint (`after_ms`, `max`).
- Mutating requests accept an `Idempotency-Key` header — reuse the same key when retrying so the operation is applied once.

---

## Integration checklist for coding agents

1. Store the API key in an env var (`APP_API_KEY`); never commit it.
2. Store the org id (`APP_ORG_ID`) alongside it.
3. Base URL `https://your-domain.com/api`; all org endpoints are under `/orgs/{org_id}/…`.
4. Handle `401` (revoked key), `402`/`409` credit errors, and `429` with backoff honoring `Retry-After`.
5. Send `Idempotency-Key` on POSTs you might retry.
6. Poll async jobs (LLM calls, generations) until `status` leaves `pending`.
7. The template's AI endpoints require a session JWT; API keys cover the credits
   read endpoints and any metered endpoints you add with `CurrentMember` auth.

---

## Links

- Dashboard: https://your-domain.com/dashboard
- API keys: https://your-domain.com/api-keys
- Billing & credits: https://your-domain.com/billing
- Human docs: https://your-domain.com/docs
