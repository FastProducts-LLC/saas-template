# Product analytics

Answers "what is used, by whom, and what actually converts" with two sinks
behind one `track()` facade:

| Sink | Where | Who is recorded | Gated by |
|---|---|---|---|
| **First-party** | `activity_events` table in the app database | Signed-in users only | The account's opt-out (Profile → Privacy). Not the cookie banner. |
| **Google Analytics 4** | Google, via gtag.js in the browser | Any visitor | Cookie-banner consent, then the account's opt-out. Inert without `VITE_GA_MEASUREMENT_ID`. |

The table is the source of truth for DAU/retention/funnels: it survives ad
blockers and consent declines, and you own it. GA adds anonymous traffic,
sources, and page views, which the table deliberately does not hold.

## Decisions

- **Consent.** The first-party table stores nothing on, and reads nothing
  from, the visitor's device — it is a server-side record under an
  authenticated session — so it is processed on legitimate interest and is
  **not** gated on the cookie banner. What makes that defensible: an honored
  opt-out, disclosure in the privacy policy, a deletion cascade, and no
  content in properties. This is an engineering default, **not legal advice**;
  have counsel confirm it for your market. To gate the table on the banner as
  well, add `if (!consentAllows("analytics")) return;` to `sendFirstParty` in
  `frontend/src/shared/lib/track.ts` and accept the undercount.
- **No anonymous rows.** `user_id` is `NOT NULL`. Anonymous questions belong
  to GA.
- **Page views are GA-only.** They multiply row volume 10–50x and add nothing
  to DAU.
- **Server events go to the table only.** The backend never sends anything to
  Google (no Measurement Protocol), so the cookie banner fully describes what
  Google receives.
- **Activation event: `generation_completed`** — the first delivered AI
  generation. Written server-side, so web, mobile, and API-key callers all
  count. If you replace the flagship feature, move activation with it.
- **Opt-out ≠ consent.** Two independent switches. Cookie consent decides
  whether the GA tag loads for a *browser*. `users.analytics_opt_out` silences
  both sinks for an *account*, on every device, including server events.
  Opting out stops future rows; it does not delete past ones (that is the
  account-deletion / privacy-request path).
- **Retention: 730 days**, `[analytics].activity_event_retention_days` in
  `shared/policy.toml`. The privacy policy quotes it ("24 months") — change
  both together.

## How it fits together

```
shared/events.toml ──gen_events.py──┬─► frontend/src/shared/lib/events.ts
                                    └─► backend/app/domains/analytics/domain/events.py

browser:  track(EVENTS.x, params)            frontend/src/shared/lib/track.ts
            ├─► GA4 (analytics.ts)           consent + not opted out
            └─► POST /api/events             signed in + not opted out
                  └─► activity_events (source = 'client')

backend:  tracker.capture_server_event(user_id, "x", {...})
                  └─► activity_events (source = 'server')
```

### Client

Call sites import only `track` and `EVENTS`:

```ts
import { EVENTS } from "../../../shared/lib/events";
import { track } from "../../../shared/lib/track";

onSuccess: () => {
  track(EVENTS.invite_sent, { role: vars.role });
  return queryClient.invalidateQueries(...);
}
```

- Fire **once**, at the **success point** (mutation `onSuccess`), never on click.
- `track` is typed to client events; passing a server event is a compile error.
- Identity is wired in `features/auth/model/session.tsx`: `identifyUser` on
  login, session restore, and `refreshUser`; `resetAnalytics` on successful
  logout; all sinks are suspended while an admin impersonates a user.
- Registry `ga = "..."` aliases send GA its recommended event name
  (`sign_up`, `login`, `begin_checkout`); the table always stores the
  registry name.

### Ingest — `POST /api/events`

Body `{"event": "<name>", "properties": {...}}`.

- `401` without a session; **`204` for every authenticated request**, stored
  or dropped — no validation oracle, and the client is fire-and-forget.
- The user is the session's user. A `user_id` in the body is ignored.
- Only `[client.*]` names are accepted; server-truth names posted by a browser
  are dropped.
- Properties: object root, ≤25 keys, snake_case keys, scalar values, strings
  truncated to 100 chars, body ≤ 8 KB. Invalid keys are dropped individually.
- 60 events/user/minute (Redis, fail-open). Over-limit events are dropped
  silently, not 429'd.

### Server truth

Slices declare a minimal `ActivityTracker` Protocol in their own
`application/ports.py`; composition roots (request deps *and* worker entry
points) pass `build_activity_tracker(session)`:

```python
await self.analytics.capture_server_event(
    event.user_id, "credit_pack_purchased", {"pack": event.pack, "credits": event.credits}
)
```

The write happens in a SAVEPOINT on the caller's transaction, so the event
commits or rolls back **with** the business change (a rolled-back grant
leaves no phantom purchase), while an analytics failure only unwinds the
savepoint. It never raises, and it silently skips when `user_id` is `None`
(API-key actors), the user opted out, or the name is not a registered server
event (logged at error level — that is a typo).

Use a **literal** event name in the call: the registry audit matches literals.

## Coverage matrix

| Area | Applies | Events | Sink |
|---|---|---|---|
| 1. Acquisition & landing | yes | `cta_clicked` | GA (anonymous) |
| 2. Onboarding & activation | yes | `onboarding_tour_completed`, `onboarding_tour_skipped` (dashboard tour); `generation_completed` is the activation marker | both / table |
| 3. Auth & account | yes | `signup_started`, `user_signed_up`, `user_logged_in`, `user_logged_out`, `password_reset_requested` | both (anonymous ones GA-only) |
| 4. Core feature usage | yes | `generation_requested`, `generation_completed`, `generation_failed`, `llm_call_completed` | table (server) |
| 5. Monetization | yes | client intent: `checkout_started`, `billing_portal_opened`; server truth: `credit_pack_purchased`, `community_subscription_activated`, `community_subscription_canceled` | both / table |
| 6. Collaboration | yes | `org_created`, `invite_sent`, `invite_accepted` | both |
| 7. Retention loops | no | no notifications/favorites in the template | — |
| 8. Settings & extensibility | yes | `api_key_created`, `api_key_revoked`, `settings_updated` | both |
| 9. Content & public surface | yes | none by design — blog/docs are page views | GA page views |
| 10. Support & feedback | no | no feedback surface in the template | — |
| 11. Programmatic surface | partial | API-key calls have no user, so they are not in the table; generations/LLM calls made by a signed-in user are | see gaps |
| Unique: community | yes | `community_joined`, `community_profile_updated`, `community_conversation_started`, `community_message_sent` | both |

### Known gaps (deliberate, revisit when they matter)

- **Admin console mutations** (`/admin/*`) are not tracked: operator actions
  are in `admin_audit_log`, and they are not product usage.
- **Mobile app client events.** The Expo app does not call `/api/events`.
  Its core usage still lands in the table through the server-truth events;
  what is missing is mobile UI events (login, invites). Port `track.ts` to
  `mobile/src/shared/lib` when that matters.
- **API-key traffic.** Requests authenticated by an API key have no
  `users.id`, and the table requires one. Per-key usage is already in the
  credits ledger (`/orgs/{id}/credits/usage`).
- **`payment_failed` / `past_due`.** Community `past_due` keeps premium for a
  grace window and emits nothing; only the free↔premium transitions are
  events.
- **Purchases from checkout sessions created before this change** carry no
  buyer id in their Stripe metadata: credits are granted as usual, no
  analytics row is written.

## Adding an event

1. Add a `[client.<name>]` or `[server.<name>]` table to `shared/events.toml`
   (snake_case `object_action`, ≤40 chars; `params` are identifiers, enums,
   numbers).
2. `python3 scripts/gen_events.py`
3. Call `track(EVENTS.<name>, …)` in the mutation hook's `onSuccess`, or
   `capture_server_event(user_id, "<name>", …)` in the use case.
4. If it introduces a new *category* of data, update
   `frontend/src/features/legal/PRIVACY_POLICY.md` in the same change.

Names are permanent once shipped (historical rows keep them): to rename, add
a new event and stop firing the old one.

**Never** put content in properties — prompts, message bodies, names, emails,
tokens, free-text error messages. The server-side sanitizer is a backstop,
not permission.

## Queries

```sql
-- DAU / WAU / MAU
SELECT
  count(DISTINCT user_id) FILTER (WHERE created_at >= now() - interval '1 day')   AS dau,
  count(DISTINCT user_id) FILTER (WHERE created_at >= now() - interval '7 days')  AS wau,
  count(DISTINCT user_id) FILTER (WHERE created_at >= now() - interval '30 days') AS mau
FROM activity_events;

-- Activation rate of the last 30 days' signups
WITH signups AS (
  SELECT DISTINCT user_id FROM activity_events
  WHERE event = 'user_signed_up' AND created_at >= now() - interval '30 days'
)
SELECT count(*) AS signed_up,
       count(*) FILTER (WHERE EXISTS (
         SELECT 1 FROM activity_events a
         WHERE a.user_id = s.user_id AND a.event = 'generation_completed')) AS activated
FROM signups s;

-- Checkout funnel (client intent -> server truth)
SELECT
  count(DISTINCT user_id) FILTER (WHERE event = 'checkout_started')      AS started,
  count(DISTINCT user_id) FILTER (WHERE event = 'credit_pack_purchased') AS purchased
FROM activity_events
WHERE created_at >= now() - interval '30 days';

-- What is actually used, last 7 days
SELECT event, source, count(*) AS times, count(DISTINCT user_id) AS users
FROM activity_events
WHERE created_at >= now() - interval '7 days'
GROUP BY event, source ORDER BY users DESC;
```

## Operations

- **Purge:** beat task `purge-activity-events` runs daily at 05:15 UTC and
  deletes rows past retention in 10k-row batches, one transaction per batch.
- **Account deletion** cascades (`ON DELETE CASCADE` on `user_id`).
- **Scale:** 1k DAU × 30 events/day ≈ 11M rows/year — unremarkable for
  Postgres with the three indexes. Past ~100k DAU, switch to monthly
  partitions on `created_at`.
- **GA setup** (Measurement ID, CSP, CI build arg) is in
  `docs/customization.md` §6.3; changing the ID requires a frontend rebuild.
- **Drift check:** CI runs `python3 scripts/gen_events.py --check`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Event in the table, not in GA | Expected when the visitor declined cookies or runs an ad blocker — that is why the table exists. Otherwise check the banner choice and the CSP. |
| Event in GA, not in the table | User not signed in at that moment, account opted out, name not in `[client.*]`, or rate-limited. Backend debug logs say which. |
| No rows at all for one user | `users.analytics_opt_out` is true. |
| Server event missing | `user_id` was `None`, the user opted out, or the name is unregistered (error log: "is not a registered server event"). |
| Zero GA events ever | Measurement ID missing at build time, or CSP blocks `googletagmanager.com`. |
