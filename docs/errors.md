<!-- GENERATED FILE — do not edit by hand. Source: shared/errors.toml (python3 scripts/gen_errors.py) -->

# Error Code Reference

Support lookup table. Users report `code · ref` (the ref is the request's
`error_id`); a superuser can fetch the full request context with
`GET /api/admin/errors/{error_id}`.

## `ERR_REQ_001` — Request could not be processed

- **HTTP status:** 400
- **Severity:** warning · **Display:** toast
- **User sees:** We couldn't process that request. *Try again. If it keeps happening, contact support and mention the code shown below.*
- **Technical context:** Base AppError fallback — a slice raised AppError directly instead of a specific subclass. Treat occurrences as a prompt to define a dedicated code.

## `ERR_REQ_002` — Not found

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** We couldn't find that page or it may have been removed. *Check the link, or head back to your dashboard.*
- **Technical context:** Generic NotFoundError or an unmatched route (Starlette 404/405 are mapped here too).

## `ERR_REQ_003` — Conflict

- **HTTP status:** 409
- **Severity:** info · **Display:** toast
- **User sees:** That change conflicts with the current state of your data. *Refresh to see the latest version, then try again.*
- **Technical context:** Generic ConflictError fallback. Prefer a specific code (ERR_VAL_006 for stale writes, ERR_ORG_*/ERR_BILL_* for domain conflicts).

## `ERR_REQ_004` — Too many requests

- **HTTP status:** 429
- **Severity:** warning · **Display:** toast
- **User sees:** You're doing that a little too fast, so we've paused things briefly. *Wait a moment, then try again.*
- **Technical context:** RateLimited raised by a rate-limiting dependency (Redis sliding window — provisioned but opt-in). Retry-After is set when known; the frontend disables the triggering control until it elapses.
- **⚠ Ops signal:** Burst from a single IP/user on /auth/login = credential stuffing attempt.

## `ERR_REQ_005` — Payload too large

- **HTTP status:** 413
- **Severity:** info · **Display:** toast
- **User sees:** That file or request is too large for us to accept. *Try something smaller, or compress the file first.*
- **Technical context:** Frontend-mapped from a (often bodyless) 413 — usually rejected by the proxy before reaching FastAPI, so no problem+json body exists.

## `ERR_VAL_001` — Validation failed

- **HTTP status:** 422
- **Severity:** info · **Display:** field
- **User sees:** Some of the information looks incomplete or incorrect. *Check the highlighted fields and try again.*
- **Technical context:** Pydantic schema validation failed at the router boundary. The handler flattens pydantic's loc list into the envelope's `fields` map (keys are dotted body paths, with the body/query/path prefix dropped) and rewrites pydantic's messages into plain sentences (`friendly_field_message` in app.core.error_handling). Custom validator ValueErrors pass through minus pydantic's 'Value error, ' prefix, so write them as user-facing copy.
- **⚠ Ops signal:** Concentrated on one field right after a deploy = frontend/backend schema drift.

## `ERR_VAL_002` — Email already registered

- **HTTP status:** 409
- **Severity:** info · **Display:** field
- **User sees:** An account with this email already exists. *Try signing in instead, or use 'Forgot password' if you don't remember it.*
- **Technical context:** EmailAlreadyRegistered from AuthService.register (caught before the unique constraint fires). Only raised when SIGNUP_ENUMERATION_PROTECTION is off (the default): a deliberate enumeration trade-off for one-step signup, bounded by the register rate limit. With it on, register answers 202 verification_required either way, the existing owner gets a notice email, and this error never fires.

## `ERR_VAL_003` — Password too weak

- **HTTP status:** 400
- **Severity:** info · **Display:** field
- **User sees:** That password is too easy to guess. *Use at least 12 characters with a mix of letters and numbers, avoiding common passwords.*
- **Technical context:** PasswordTooWeak — validate_password_strength failed (too short, missing letter/digit mix, or on the common-password blocklist). Min length is PASSWORD_MIN_LENGTH in auth/domain/services.py (mirrored in frontend password-policy).

## `ERR_VAL_004` — Passwords do not match

- **HTTP status:** 400
- **Severity:** info · **Display:** field
- **User sees:** The two passwords you entered don't match. *Re-type both passwords so they match exactly.*
- **Technical context:** PasswordMismatch from AuthService.register. Normally caught client-side first; reaching the backend implies JS-less submission or a frontend bug.

## `ERR_VAL_005` — Terms not accepted

- **HTTP status:** 400
- **Severity:** info · **Display:** field
- **User sees:** You'll need to accept the Terms of Service and Privacy Policy to create an account. *Tick the agreement checkbox, then try again.*
- **Technical context:** TermsNotAccepted from AuthService.register — terms_accepted was false at the API boundary.

## `ERR_VAL_006` — Edit conflict

- **HTTP status:** 409
- **Severity:** info · **Display:** toast
- **User sees:** Someone else changed this just now, so we didn't save your edits to avoid overwriting theirs. *Refresh to see the latest version, then re-apply your changes.*
- **Technical context:** StaleWriteError — optimistic concurrency failure (stale version/updated_at on write). Log both versions' timestamps and the conflicting user_id. Defined in core for slices to adopt.

## `ERR_AUTH_001` — Invalid credentials

- **HTTP status:** 401
- **Severity:** info · **Display:** field
- **User sees:** That email and password combination didn't match our records. *Double-check both fields and try again, or use 'Forgot password' to reset it.*
- **Technical context:** InvalidCredentials from AuthService.login: user not found OR argon2 verify failed — logged identically for both to prevent user-enumeration timing analysis.

## `ERR_AUTH_002` — Session expired

- **HTTP status:** 401
- **Severity:** info · **Display:** page
- **User sees:** Your session has ended, so we signed you out to keep your account safe. *Sign in again to pick up where you left off.*
- **Technical context:** SessionExpired on the refresh path: cookie missing, token expired (>30d), or hash mismatch after rotation (possible reuse/theft — the token family is revoked). Surfaces when the frontend's transparent tryRefresh() fails; the auth context then signs the user out.

## `ERR_AUTH_003` — Could not verify sign-in

- **HTTP status:** 401
- **Severity:** warning · **Display:** toast
- **User sees:** We couldn't verify your sign-in. *Refresh the page. If you're still stuck, sign out and back in.*
- **Technical context:** Generic AuthenticationError from auth deps: missing bearer, malformed/bad-signature JWT, or inactive user — distinct from simple expiry (silently refreshed). Often clock skew or a SECRET_KEY mismatch across instances.
- **⚠ Ops signal:** Spike right after a deploy = SECRET_KEY mismatch between instances — roll back.

## `ERR_AUTH_004` — Link invalid or expired

- **HTTP status:** 400
- **Severity:** info · **Display:** page
- **User sees:** This link is no longer valid — it may have expired or already been used. *Request a fresh link and use it soon after it arrives.*
- **Technical context:** InvalidActionToken: a purpose-scoped action JWT (email verification or password reset) failed decode, expired, had a purpose mismatch, or the password-reset fingerprint no longer matches (link already used, or the password changed after it was issued). TTLs: EMAIL_VERIFICATION_TTL_HOURS / PASSWORD_RESET_TTL_MINUTES.

## `ERR_AUTH_005` — Email not verified

- **HTTP status:** 403
- **Severity:** info · **Display:** toast
- **User sees:** Confirm your email address before continuing. *Check your inbox for the verification link, or resend it from your profile.*
- **Technical context:** EmailNotVerified — EMAIL_VERIFICATION_GATE is sensitive/login and the session user has email_verified_at IS NULL. CurrentVerifiedUser (and LoginUser when gate=login) raise this. API-key callers are not gated. Flip the gate in Settings / env per project.

## `ERR_AUTH_006` — Account temporarily locked

- **HTTP status:** 429
- **Severity:** warning · **Display:** field
- **User sees:** Too many failed sign-in attempts, so sign-in for this account is paused briefly. *Wait about 15 minutes and try again, or reset your password now via 'Forgot password'.*
- **Technical context:** AccountTemporarilyLocked from LoginUser: LOGIN_LOCKOUT_MAX_ATTEMPTS consecutive failures within LOGIN_LOCKOUT_WINDOW_MINUTES from one client IP lock that email for that IP only; LOGIN_LOCKOUT_ACCOUNT_MAX_ATTEMPTS failures across all IPs lock the email for everyone. Both are tracked whether or not the account exists (no enumeration signal); a completed password reset lifts the lock. Redis-backed; on a Redis outage it degrades to a per-process in-memory counter (never fully open). Retry-After carries the remaining lock seconds.
- **⚠ Ops signal:** A spike here = credential-stuffing campaign — query audit_events for auth.lockout_triggered grouped by ip. meta.scope=account means an email was locked for every client, its owner included (distributed guessing or a targeted lockout).

## `ERR_AUTH_007` — Not available while impersonating

- **HTTP status:** 403
- **Severity:** warning · **Display:** toast
- **User sees:** This action isn't available while you're viewing the app as another user. *End the impersonation session and ask the account owner to do this themselves.*
- **Technical context:** ImpersonationNotAllowed from forbid_impersonation (auth/interface/deps.py): the access token carries an `imp` claim (admin impersonation session) and the route creates or changes a credential that would outlive the 15-minute session (password change, API key creation). Impersonation is for looking, not for minting persistent access.

## `ERR_PERM_001` — Permission denied

- **HTTP status:** 403
- **Severity:** info · **Display:** toast
- **User sees:** You don't have permission to do that in this organization. *Ask an organization admin to upgrade your role, or switch to an organization where you have access.*
- **Technical context:** InsufficientRole (or base PermissionDeniedError): require_role() passed the membership check but the role rank was insufficient. Log includes org_id, user_id, required vs. actual role.

## `ERR_PERM_002` — Not found

- **HTTP status:** 404
- **Severity:** warning · **Display:** toast
- **User sees:** We couldn't find that page or it may have been removed. *Check the link, or head back to your dashboard.*
- **Technical context:** OrganizationNotFound — deliberate 404-masking per multi-tenancy rule #2: the user is NOT a member of the requested org, and org existence must never leak. The internal log records the real reason; the user copy is identical to a plain 404.
- **⚠ Ops signal:** Burst from one user across many org_ids = tenant-enumeration probing — security signal.

## `ERR_PERM_003` — Invitation invalid

- **HTTP status:** 404
- **Severity:** info · **Display:** page
- **User sees:** This invitation is no longer valid. *Ask the person who invited you to send a new invitation.*
- **Technical context:** InvitationInvalid: token expired (>7d), already accepted, or revoked. Log which of the three — a high expired rate suggests the TTL is too short.

## `ERR_PERM_004` — Administrator access required

- **HTTP status:** 403
- **Severity:** warning · **Display:** page
- **User sees:** This area is for platform administrators. *Head back to your dashboard. If you believe you should have access, contact an existing administrator.*
- **Technical context:** NotSuperuser from get_current_superuser — a signed-in non-superuser hit an /admin route. is_superuser is only granted manually in the database.
- **⚠ Ops signal:** Repeated hits from one user = someone probing the admin surface.

## `ERR_ORG_001` — Last owner

- **HTTP status:** 409
- **Severity:** info · **Display:** toast
- **User sees:** An organization needs at least one owner, and this is the only one. *Make someone else an owner first, then try again.*
- **Technical context:** LastOwnerError — attempted to demote/remove the sole owner. Raised by OrganizationService role-change/removal paths.

## `ERR_ORG_002` — Already a member

- **HTTP status:** 409
- **Severity:** info · **Display:** toast
- **User sees:** That person is already a member of this organization. *Nothing to do — they already have access. Check the Members page.*
- **Technical context:** AlreadyMember — invitation or acceptance for a user who already holds a membership in the org.

## `ERR_ORG_003` — Member not found

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** We couldn't find that member in this organization. *Refresh the Members page — they may have already been removed.*
- **Technical context:** MemberNotFound — membership id valid-shaped but no row in this org (already removed, or cross-org id). Repos filter by organization_id, so cross-tenant ids land here by design.

## `ERR_ORG_004` — Organization suspended

- **HTTP status:** 403
- **Severity:** warning · **Display:** page
- **User sees:** This organization has been suspended. *Contact support to resolve the suspension.*
- **Technical context:** OrgSuspended — organizations.suspended_at is set; require_role blocks every /orgs/{org_id}/* route for all members. Set/cleared by platform admins via /admin/organizations/{id}/(un)suspend.

## `ERR_ORG_005` — Domain not claimable

- **HTTP status:** 400
- **Severity:** info · **Display:** toast
- **User sees:** That domain can't be claimed for this organization. *Use your company's own domain — it must match your email address, and shared providers like gmail.com aren't allowed.*
- **Technical context:** DomainNotClaimable — normalize_claimable_domain rejected the claim: malformed domain, public mailbox provider, owner's email not on the domain, owner email unverified, or DOMAIN_CLAIM_MODE=off.

## `ERR_ORG_006` — Domain already claimed

- **HTTP status:** 409
- **Severity:** info · **Display:** toast
- **User sees:** Another organization has already claimed that domain. *If this is your company's domain, contact support to resolve the conflict.*
- **Technical context:** DomainAlreadyClaimed — organizations.email_domain is unique; a different org row already holds this domain.

## `ERR_ORG_007` — Company workspace already exists

- **HTTP status:** 409
- **Severity:** info · **Display:** field
- **User sees:** Your company already has a workspace. *Verify your email to join automatically, or ask your company's workspace owner for an invitation.*
- **Technical context:** DomainOrgExists — CreateOrganization blocked because an org already claims this user's email domain. The user should auto-join via email verification instead.

## `ERR_ADM_001` — User not found

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** No user matches that id. *Refresh the user list — the account may have been removed.*
- **Technical context:** AdminUserNotFound — admin lookup by user id missed. Staff-facing copy; plainer than tenant-facing equivalents.

## `ERR_ADM_002` — Organization not found

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** No organization matches that id. *Refresh the organization list — it may have been deleted.*
- **Technical context:** AdminOrgNotFound — admin lookup by org id missed. Unlike ERR_PERM_002, this is NOT masked: the caller is already a superuser.

## `ERR_ADM_003` — Cannot deactivate yourself

- **HTTP status:** 409
- **Severity:** info · **Display:** toast
- **User sees:** You can't deactivate your own account from here. *Ask another administrator to do it, so the platform is never left without an active admin.*
- **Technical context:** CannotDeactivateSelf — self-deactivation guard on the admin users endpoint.

## `ERR_ADM_004` — Error record not found

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** No error record matches that reference. *Check the reference for typos — records also expire after 7 days.*
- **Technical context:** AdminErrorRecordNotFound — /admin/errors/{error_id} lookup missed in Redis (expired errctx TTL or a mistyped reference).

## `ERR_ADM_005` — Cannot impersonate a superuser

- **HTTP status:** 409
- **Severity:** warning · **Display:** toast
- **User sees:** Superuser accounts can't be impersonated. *Impersonation is for regular accounts only — coordinate with the other admin directly.*
- **Technical context:** CannotImpersonateSuperuser — impersonation guard. Also covers self-impersonation (the acting user is a superuser by definition).

## `ERR_ADM_006` — Cannot impersonate a deactivated user

- **HTTP status:** 409
- **Severity:** info · **Display:** toast
- **User sees:** That account is deactivated, so it can't be impersonated. *Reactivate the account first if you need to see it from the inside.*
- **Technical context:** CannotImpersonateInactive — impersonation guard on users with is_active = false.

## `ERR_ADM_007` — Invitation not found

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** No pending invitation matches that id. *Refresh the invitations list — it may already be accepted or revoked.*
- **Technical context:** AdminInvitationNotFound — cross-tenant invitation lookup missed, or the invitation was already accepted.

## `ERR_ADM_008` — Invalid merge

- **HTTP status:** 409
- **Severity:** warning · **Display:** toast
- **User sees:** Cannot merge these organizations. *The target and source organizations must be different, existing organizations.*
- **Technical context:** MergeInvalid — admin org-merge guard: target not found, source not found, or source == target.

## `ERR_CRD_001` — Not enough credits

- **HTTP status:** 409
- **Severity:** info · **Display:** toast
- **User sees:** Your organization doesn't have enough credits for this. *Buy a credit pack, then try again.*
- **Technical context:** InsufficientCredits — the reservation would take the org balance below zero. Sends `required` (action cost) and `available` (current balance) as params.
- **Params:** `required`, `available` → *This needs {required} credits, but your organization has {available}.*
- **⚠ Ops signal:** A wave across many orgs after a deploy = an action's credit cost was misconfigured.

## `ERR_CRD_002` — Action already settled

- **HTTP status:** 409
- **Severity:** info · **Display:** toast
- **User sees:** That action was already completed or cancelled. *Refresh to see the current state — no credits were double-charged.*
- **Technical context:** ReservationNotActive — finalize/cancel attempted on a non-active credit reservation. This is the double-settlement guard working as intended.

## `ERR_CRD_003` — Reservation not found

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** We couldn't find that pending action. *Refresh and try again from the start.*
- **Technical context:** ReservationNotFound — reservation id missing for this org (repos filter by organization_id, so cross-tenant ids land here by design).

## `ERR_CRD_004` — Unknown action

- **HTTP status:** 409
- **Severity:** warning · **Display:** toast
- **User sees:** That action isn't available. *Refresh the page — you may be on an older version of the app.*
- **Technical context:** UnknownAction — credit-cost lookup for an action key that isn't in the pricing table. Usually a stale frontend bundle or a missing pricing entry for a newly shipped action.

## `ERR_CRD_005` — Unknown credit pack

- **HTTP status:** 409
- **Severity:** warning · **Display:** toast
- **User sees:** That credit pack isn't available. *Refresh the page and pick one of the listed packs.*
- **Technical context:** UnknownCreditPack — a CreditPack value missing from the CREDIT_PACKS catalog. Stale frontend bundle, or webhook metadata referencing a pack that was removed from the catalog.

## `ERR_CRD_006` — Member credit limit reached

- **HTTP status:** 409
- **Severity:** info · **Display:** toast
- **User sees:** You've reached your monthly credit limit for this organization. *Ask an organization admin to raise your limit, or try again next month.*
- **Technical context:** MemberCreditLimitExceeded — the acting user's captured + pending reservations this UTC calendar month plus the requested cost exceed member_credit_limits.monthly_limit. API-key charges are exempt (they carry no user_id). The error message includes used vs. requested amounts.

## `ERR_CRD_007` — Not an organization member

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** That person isn't a member of this organization. *Check the member list and try again.*
- **Technical context:** LimitTargetNotMember — a member-limit set referenced a user_id with no membership in the org (removed member or wrong id).

## `ERR_GEN_001` — Generation not found

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** We couldn't find that generation. *Head back to your generations list — it may have been removed.*
- **Technical context:** GenerationNotFound — generation id missing for this org.

## `ERR_GEN_002` — Generation not available

- **HTTP status:** 409
- **Severity:** warning · **Display:** toast
- **User sees:** Content generation isn't set up on this server yet. *If you run this deployment, configure the provider API keys (see README). Otherwise, contact your administrator.*
- **Technical context:** ProviderNotConfigured — the generation provider's API key is empty. Expected in fresh dev environments; in production it's env misconfiguration.

## `ERR_GEN_003` — Generation failed

- **HTTP status:** 409
- **Severity:** error · **Display:** toast
- **User sees:** We couldn't finish generating that, and your credits for it have been returned. *Try again. If it keeps failing, tweak your input or contact support with the code below.*
- **Technical context:** GenerationFailed — the provider call errored; the credit reservation is released (refund), which is what makes the 'credits returned' promise honest. Log the provider error verbatim.
- **⚠ Ops signal:** Sustained rate = provider outage or a prompt/template regression — check provider status first.

## `ERR_GEN_004` — Still generating

- **HTTP status:** 409
- **Severity:** info · **Display:** toast
- **User sees:** This is still being generated. *Give it a few seconds — the result will appear when it's ready.*
- **Technical context:** ResultNotReady — result fetched before the generation finished. Normal during polling; only worth attention if a generation never leaves this state.

## `ERR_GEN_005` — Can't cancel this

- **HTTP status:** 409
- **Severity:** info · **Display:** toast
- **User sees:** This can only be canceled while it's still generating. *It already finished — refresh to see the result.*
- **Technical context:** NotCancelable — cancel requested on a non-pending generation. Usually a race between the user clicking cancel and the job finishing; harmless.

## `ERR_GEN_006` — Can't delete this yet

- **HTTP status:** 409
- **Severity:** info · **Display:** toast
- **User sees:** Wait until this finishes before deleting it. *Cancel it first, then delete it.*
- **Technical context:** NotDeletable — delete requested on a still-pending generation. Deleting mid-flight would orphan the credit hold and the in-progress provider job; cancel handles those.

## `ERR_PRIV_001` — Privacy request not found

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** We couldn't find that privacy request. *Refresh the queue — it may have been closed or the link is stale.*
- **Technical context:** PrivacyRequestNotFound — admin lookup by privacy request id missed.

## `ERR_PRIV_002` — Privacy request cannot be updated

- **HTTP status:** 409
- **Severity:** info · **Display:** toast
- **User sees:** That privacy request is not in a state that allows this action. *Check the current status, then use the next allowed step (verify → fulfill/forward → close).*
- **Technical context:** PrivacyRequestInvalidTransition — status machine guard on verify/fulfill/forward/close/reject.

## `ERR_PRIV_003` — Privacy request incomplete

- **HTTP status:** 400
- **Severity:** info · **Display:** field
- **User sees:** We need a bit more information to process this privacy request. *Provide a contact email plus an email or phone number for the subject.*
- **Technical context:** PrivacyRequestIncomplete — missing required intake or ops fields (contact email, subject locator, provider ref, rejection reason).

## `ERR_LLM_001` — AI text provider not configured

- **HTTP status:** 409
- **Severity:** warning · **Display:** toast
- **User sees:** This AI text provider isn't set up on this server yet. *If you run this deployment, add the provider API key (see README). Otherwise, contact your administrator.*
- **Technical context:** LlmProviderNotConfigured — GEMINI_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY empty for the requested provider. Raised before any credits are held.

## `ERR_LLM_002` — Text generation failed

- **HTTP status:** 409
- **Severity:** error · **Display:** toast
- **User sees:** The AI provider couldn't complete this request, and your credit for it has been returned. *Try again. If it keeps failing, switch providers or contact support with the code below.*
- **Technical context:** LlmCallFailed — the provider call errored or returned no text. The credit hold is released before this is raised, which is what makes the 'credit returned' promise honest. A FAILED llm_calls row records the provider error verbatim.
- **⚠ Ops signal:** Sustained rate on one provider = provider outage or quota exhaustion — check the provider status page and API quota.

## `ERR_LLM_003` — Text completion not found

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** We couldn't find that text completion. *Head back to your completions list — it may have been removed.*
- **Technical context:** LlmCallNotFound — llm call id missing for this org, or a non-UUID id was requested on the poll endpoint.

## `ERR_BILL_001` — Billing not configured

- **HTTP status:** 409
- **Severity:** warning · **Display:** toast
- **User sees:** Payments aren't set up on this server yet. *If you run this deployment, add your Stripe keys (see README). Otherwise, contact your administrator.*
- **Technical context:** BillingNotConfigured — STRIPE_SECRET_KEY is empty. Expected in fresh dev environments; in production it means env misconfiguration.

## `ERR_BILL_002` — Payment provider unreachable

- **HTTP status:** 502
- **Severity:** critical · **Display:** toast · **Auto-retry:** 2× after 2000ms
- **User sees:** We couldn't reach our payment provider just now. You have not been charged. *Wait a moment and try again. Your credits and data are unaffected.*
- **Technical context:** StripeUnavailable — Stripe API connection error / 5xx / rate limit during checkout, portal, or customer creation. Log the stripe request id. 'You have not been charged' is the critical UX line — payment errors create disproportionate anxiety.
- **⚠ Ops signal:** More than a handful in 5 minutes = Stripe incident or egress problem — check status.stripe.com.

## `ERR_BILL_004` — No billing account

- **HTTP status:** 409
- **Severity:** warning · **Display:** toast
- **User sees:** This organization doesn't have a billing account yet. *Buy a credit pack first — that sets up billing automatically.*
- **Technical context:** NoBillingAccount — Customer Portal requested before any checkout created a Stripe customer.

## `ERR_BILL_006` — Credit pack not purchasable

- **HTTP status:** 409
- **Severity:** warning · **Display:** toast
- **User sees:** That credit pack can't be purchased right now. *Pick another pack, or contact your administrator if none work.*
- **Technical context:** PackNotPurchasable — a credit pack was requested whose Stripe price id is unset (STRIPE_PRICE_CREDITS_*).

## `ERR_BILL_007` — Membership plan not available

- **HTTP status:** 409
- **Severity:** warning · **Display:** toast
- **User sees:** That membership plan can't be purchased right now. *Try the other plan, or contact support if none work.*
- **Technical context:** CommunityPlanNotConfigured — a community membership checkout was requested but the plan's Stripe price id is unset (STRIPE_PRICE_COMMUNITY_*).

## `ERR_BILL_008` — Organization plan not available

- **HTTP status:** 409
- **Severity:** warning · **Display:** toast
- **User sees:** That organization plan can't be purchased right now. *Choose another plan or contact your administrator.*
- **Technical context:** PlanNotConfigured — a paid organization plan has no Stripe price id for the requested interval (STRIPE_PRICE_PLAN_*).

## `ERR_BILL_009` — Subscription already active

- **HTTP status:** 409
- **Severity:** warning · **Display:** toast
- **User sees:** This organization already has an active paid subscription. *Manage your existing plan through the billing portal.*
- **Technical context:** SubscriptionAlreadyActive — checkout requested while the organization already has a live paid subscription.

## `ERR_FILE_001` — File not found

- **HTTP status:** 404
- **Severity:** warning · **Display:** toast
- **User sees:** We couldn't find that file. *Refresh and try again, or upload the file again if it was removed.*
- **Technical context:** FileNotFound — the requested file does not exist or is outside the caller's ownership scope.

## `ERR_FILE_002` — Upload too large

- **HTTP status:** 413
- **Severity:** warning · **Display:** toast
- **User sees:** That file is too large to upload. *Choose a smaller file within the size limit shown.*
- **Technical context:** UploadTooLarge — the declared or actual upload size exceeds the limit for its purpose.

## `ERR_FILE_003` — Unsupported file type

- **HTTP status:** 415
- **Severity:** warning · **Display:** toast
- **User sees:** That file type isn't supported. *Choose a file in one of the supported formats shown.*
- **Technical context:** UnsupportedFileType — the upload content type is not allowed for its purpose.

## `ERR_FILE_004` — Upload not completed

- **HTTP status:** 409
- **Severity:** warning · **Display:** toast
- **User sees:** Your file upload hasn't completed successfully. *Wait for the upload to finish, then try again. If it still fails, upload the file again.*
- **Technical context:** UploadNotCompleted — confirmation found no object, or its size or content type did not match.

## `ERR_FILE_005` — Storage unavailable

- **HTTP status:** 503
- **Severity:** error · **Display:** toast
- **User sees:** We couldn't reach file storage just now. *Wait a moment and try again.*
- **Technical context:** StorageUnavailable — the configured object storage backend could not complete the operation.

## `ERR_FILE_006` — Upload quota exceeded

- **HTTP status:** 429
- **Severity:** warning · **Display:** toast
- **User sees:** Too many uploaded files. *Set or remove your current photo, then try again.*
- **Technical context:** UploadQuotaExceeded — the owner has reached the confirmed file limit for this purpose.

## `ERR_ENT_001` — Plan upgrade required

- **HTTP status:** 403
- **Severity:** warning · **Display:** toast
- **User sees:** Your organization's plan doesn't include this feature. *Upgrade your organization's plan from Billing to use this feature.*
- **Technical context:** EntitlementRequired — the resolved entitlement limit is zero, so the feature is not included.

## `ERR_ENT_002` — Plan limit reached

- **HTTP status:** 403
- **Severity:** warning · **Display:** toast
- **User sees:** Your organization has reached its plan limit. *Upgrade your organization's plan from Billing for more capacity.*
- **Technical context:** EntitlementLimitReached — the current usage has reached the resolved organization entitlement limit. Sends `limit` (resolved cap) and `resource` (human label for the EntitlementKey) as params.
- **Params:** `limit`, `resource` → *Your organization has reached its plan limit of {limit} {resource}.*

## `ERR_ENT_003` — Unknown entitlement

- **HTTP status:** 422
- **Severity:** warning · **Display:** toast
- **User sees:** That entitlement isn't recognized. *Choose a supported entitlement and try again.*
- **Technical context:** UnknownEntitlementKey — an administrator requested an override for a key outside EntitlementKey.

## `ERR_SRV_001` — Internal server error

- **HTTP status:** 500
- **Severity:** critical · **Display:** toast
- **User sees:** Something went wrong on our end. Your data is safe, and we've been notified. *Try again in a few moments. If it keeps happening, contact support and mention the code shown below.*
- **Technical context:** Catch-all for unhandled exceptions. The handler logs the full traceback against the error_id and returns ONLY this envelope — never exception text. 'Your data is safe' is honest because get_db rolls back the transaction on failure.
- **⚠ Ops signal:** Any sustained rate is an incident. Fingerprint by error_id lookup, not by user reports.

## `ERR_SRV_002` — Request timed out

- **HTTP status:** 504
- **Severity:** error · **Display:** toast · **Auto-retry:** 2× after 2000ms
- **User sees:** This is taking longer than expected. *Wait a moment and try again — your previous attempt may still finish on its own.*
- **Technical context:** Upstream/gateway timeout (frontend-mapped from bodyless 502/504). Retrying a mutation is safe ONLY because the api client attaches an Idempotency-Key and reuses it on retry.

## `ERR_SRV_003` — Maintenance in progress

- **HTTP status:** 503
- **Severity:** warning · **Display:** page
- **User sees:** We're doing some quick maintenance and will be right back. *Nothing to fix on your end — this page will refresh itself when we're done.*
- **Technical context:** Deliberate maintenance mode or healthcheck-failed state at the proxy (frontend-mapped from a bodyless 503). The frontend shows a full-page takeover and polls /api/health with backoff, reloading when it recovers.

## `ERR_SRV_004` — Duplicate request in progress

- **HTTP status:** 409
- **Severity:** info · **Display:** toast
- **User sees:** We're still working on your previous attempt at this. *Give it a few seconds — the first attempt should finish on its own.*
- **Technical context:** Idempotency middleware: a second request arrived with the same Idempotency-Key while the first was still in flight. Usually a double-click or an aggressive client retry.

## `ERR_KEY_001` — API key not found

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** We couldn't find that API key. *Head back to the API Keys page — it may have been revoked.*
- **Technical context:** ApiKeyNotFound — API key id missing for this org (repos filter by organization_id, so cross-tenant ids land here by design).

## `ERR_BLOG_001` — Blog post not found

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** We couldn't find that blog post. *Head back to the blog — it may have been unpublished or removed.*
- **Technical context:** BlogPostNotFound — public slug lookup missed or the post isn't published (drafts/archived 404 by design), or an admin id lookup missed.

## `ERR_BLOG_002` — Slug already in use

- **HTTP status:** 409
- **Severity:** info · **Display:** field
- **User sees:** Another post already uses this slug. *Choose a different slug — each post needs a unique URL.*
- **Technical context:** BlogSlugConflict — unique-slug pre-check (or the DB unique index backstop on a race) rejected a create/update. The editor binds this to the slug field.

## `ERR_BLOG_003` — Generation job not found

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** We couldn't find that draft-generation job. *Head back to the blog admin — the job may have been cleaned up.*
- **Technical context:** BlogGenerationJobNotFound — admin polled a generation job id that doesn't exist (or a stale bookmark). Jobs are superuser-only.

## `ERR_FLAG_001` — Unknown feature flag

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** That feature flag doesn't exist. *Refresh the flags page — the list of known flags may have changed.*
- **Technical context:** UnknownFeatureFlag — a superuser tried to set a key that isn't in KNOWN_FLAGS (feature_flags/domain/entities.py). New flags must be registered there first.

## `ERR_FLAG_002` — Feature not available

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** This feature isn't available right now. *If you followed a link here, the feature may have been turned off — head back to your dashboard.*
- **Technical context:** FeatureDisabled — a require_feature() gate rejected the request because the flag is off. 404 by design so a disabled module is indistinguishable from a nonexistent route.

## `ERR_COMM_001` — Profile not found

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** We couldn't find that community member. *Head back to the member directory — they may have left or changed their handle.*
- **Technical context:** ProfileNotFound — handle/user lookup missed, or the profile is hidden (hidden profiles 404 publicly by design).

## `ERR_COMM_002` — Handle already taken

- **HTTP status:** 409
- **Severity:** info · **Display:** field
- **User sees:** Someone already uses this handle. *Pick a different handle — each member needs a unique one.*
- **Technical context:** HandleTaken — unique-handle pre-check (or the DB unique index backstop on a race) rejected a join/update. Forms bind this to the handle field.

## `ERR_COMM_003` — Not a community member

- **HTTP status:** 403
- **Severity:** info · **Display:** toast
- **User sees:** You need to join the community first. *Create your community profile, then try again.*
- **Technical context:** NotACommunityMember — an authenticated user without a community profile/membership hit a members-only route.

## `ERR_COMM_004` — Premium membership required

- **HTTP status:** 403
- **Severity:** info · **Display:** toast
- **User sees:** Messaging is part of the premium membership. *Upgrade your community membership to send messages.*
- **Technical context:** PremiumRequired — a free member (or lapsed premium past the grace window) tried a premium action. The frontend intercepts this code in community mutations and opens the upgrade prompt instead of a toast.

## `ERR_COMM_005` — Community access suspended

- **HTTP status:** 403
- **Severity:** warning · **Display:** toast
- **User sees:** Your community access has been suspended. *Contact support if you believe this is a mistake.*
- **Technical context:** CommunityBanned — a moderator banned this membership (banned_at set). All community actions are rejected; the profile is excluded from the directory.

## `ERR_COMM_006` — Conversation not found

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** We couldn't find that conversation. *Head back to your messages — the conversation may have been removed.*
- **Technical context:** ConversationNotFound — conversation id missing or the requester isn't a participant (non-participants 404 by design, no existence leak).

## `ERR_COMM_007` — Can't message yourself

- **HTTP status:** 400
- **Severity:** info · **Display:** toast
- **User sees:** You can't start a conversation with yourself. *Pick another member from the directory.*
- **Technical context:** CannotMessageSelf — StartConversation called with the requester's own handle.

## `ERR_COMM_009` — Already a premium member

- **HTTP status:** 409
- **Severity:** info · **Display:** toast
- **User sees:** You already have an active premium membership. *Manage or cancel it from your membership settings.*
- **Technical context:** AlreadyPremium — CreateCommunityCheckout called while the membership is already premium (active or in the past_due grace window). The portal is the right surface for changes.

## `ERR_COMM_008` — Member unavailable

- **HTTP status:** 404
- **Severity:** info · **Display:** toast
- **User sees:** That member can't receive messages right now. *They may have left the community — try another member.*
- **Technical context:** RecipientUnavailable — messaging target doesn't exist, is hidden, or is banned. Deliberately one 404 so moderation state never leaks.

## `ERR_NET_001` — You're offline

- **HTTP status:** — (frontend-only)
- **Severity:** info · **Display:** banner · **Auto-retry:** 2× after 1500ms
- **User sees:** We can't reach the internet right now. *Check your connection — we'll retry automatically, and anything you typed is still here.*
- **Technical context:** FRONTEND-ONLY: fetch() rejected (TypeError) — no response received, so no backend envelope exists. Synthesized by the api client. In dev, CORS failures also surface as TypeError — check the browser console.
