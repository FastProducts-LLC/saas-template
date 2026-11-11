// GENERATED FILE — do not edit by hand. Source: shared/errors.toml (python3 scripts/gen_errors.py)

export type ErrorCode =
  "ERR_REQ_001" |
  "ERR_REQ_002" |
  "ERR_REQ_003" |
  "ERR_REQ_004" |
  "ERR_REQ_005" |
  "ERR_VAL_001" |
  "ERR_VAL_002" |
  "ERR_VAL_003" |
  "ERR_VAL_004" |
  "ERR_VAL_005" |
  "ERR_VAL_006" |
  "ERR_AUTH_001" |
  "ERR_AUTH_002" |
  "ERR_AUTH_003" |
  "ERR_AUTH_004" |
  "ERR_AUTH_005" |
  "ERR_AUTH_006" |
  "ERR_AUTH_007" |
  "ERR_PERM_001" |
  "ERR_PERM_002" |
  "ERR_PERM_003" |
  "ERR_PERM_004" |
  "ERR_ORG_001" |
  "ERR_ORG_002" |
  "ERR_ORG_003" |
  "ERR_ORG_004" |
  "ERR_ORG_005" |
  "ERR_ORG_006" |
  "ERR_ORG_007" |
  "ERR_ADM_001" |
  "ERR_ADM_002" |
  "ERR_ADM_003" |
  "ERR_ADM_004" |
  "ERR_ADM_005" |
  "ERR_ADM_006" |
  "ERR_ADM_007" |
  "ERR_ADM_008" |
  "ERR_CRD_001" |
  "ERR_CRD_002" |
  "ERR_CRD_003" |
  "ERR_CRD_004" |
  "ERR_CRD_005" |
  "ERR_CRD_006" |
  "ERR_CRD_007" |
  "ERR_GEN_001" |
  "ERR_GEN_002" |
  "ERR_GEN_003" |
  "ERR_GEN_004" |
  "ERR_GEN_005" |
  "ERR_GEN_006" |
  "ERR_PRIV_001" |
  "ERR_PRIV_002" |
  "ERR_PRIV_003" |
  "ERR_LLM_001" |
  "ERR_LLM_002" |
  "ERR_LLM_003" |
  "ERR_BILL_001" |
  "ERR_BILL_002" |
  "ERR_BILL_004" |
  "ERR_BILL_006" |
  "ERR_BILL_007" |
  "ERR_BILL_008" |
  "ERR_BILL_009" |
  "ERR_FILE_001" |
  "ERR_FILE_002" |
  "ERR_FILE_003" |
  "ERR_FILE_004" |
  "ERR_FILE_005" |
  "ERR_FILE_006" |
  "ERR_ENT_001" |
  "ERR_ENT_002" |
  "ERR_ENT_003" |
  "ERR_SRV_001" |
  "ERR_SRV_002" |
  "ERR_SRV_003" |
  "ERR_SRV_004" |
  "ERR_KEY_001" |
  "ERR_BLOG_001" |
  "ERR_BLOG_002" |
  "ERR_BLOG_003" |
  "ERR_FLAG_001" |
  "ERR_FLAG_002" |
  "ERR_COMM_001" |
  "ERR_COMM_002" |
  "ERR_COMM_003" |
  "ERR_COMM_004" |
  "ERR_COMM_005" |
  "ERR_COMM_006" |
  "ERR_COMM_007" |
  "ERR_COMM_009" |
  "ERR_COMM_008" |
  "ERR_NET_001";

export type Severity = "info" | "warning" | "error" | "critical";
export type Display = "field" | "toast" | "banner" | "page";

export interface CatalogEntry {
  title: string;
  status: number;
  severity: Severity;
  display: Display;
  message: string;
  action: string;
  retry: { afterMs: number; max: number } | null;
  /** Param names the server may send for this code. */
  params?: string[];
  /** `message` with `{param}` placeholders — used only when all are present. */
  messageSpecific?: string;
  deprecated?: boolean;
}

export type ErrorParams = Record<string, string | number>;

export const errorCatalog: Record<ErrorCode, CatalogEntry> = {
  ERR_REQ_001: {"title": "Request could not be processed", "status": 400, "severity": "warning", "display": "toast", "message": "We couldn't process that request.", "action": "Try again. If it keeps happening, contact support and mention the code shown below.", "retry": null},
  ERR_REQ_002: {"title": "Not found", "status": 404, "severity": "info", "display": "toast", "message": "We couldn't find that page or it may have been removed.", "action": "Check the link, or head back to your dashboard.", "retry": null},
  ERR_REQ_003: {"title": "Conflict", "status": 409, "severity": "info", "display": "toast", "message": "That change conflicts with the current state of your data.", "action": "Refresh to see the latest version, then try again.", "retry": null},
  ERR_REQ_004: {"title": "Too many requests", "status": 429, "severity": "warning", "display": "toast", "message": "You're doing that a little too fast, so we've paused things briefly.", "action": "Wait a moment, then try again.", "retry": null},
  ERR_REQ_005: {"title": "Payload too large", "status": 413, "severity": "info", "display": "toast", "message": "That file or request is too large for us to accept.", "action": "Try something smaller, or compress the file first.", "retry": null},
  ERR_VAL_001: {"title": "Validation failed", "status": 422, "severity": "info", "display": "field", "message": "Some of the information looks incomplete or incorrect.", "action": "Check the highlighted fields and try again.", "retry": null},
  ERR_VAL_002: {"title": "Email already registered", "status": 409, "severity": "info", "display": "field", "message": "An account with this email already exists.", "action": "Try signing in instead, or use 'Forgot password' if you don't remember it.", "retry": null},
  ERR_VAL_003: {"title": "Password too weak", "status": 400, "severity": "info", "display": "field", "message": "That password is too easy to guess.", "action": "Use at least 12 characters with a mix of letters and numbers, avoiding common passwords.", "retry": null},
  ERR_VAL_004: {"title": "Passwords do not match", "status": 400, "severity": "info", "display": "field", "message": "The two passwords you entered don't match.", "action": "Re-type both passwords so they match exactly.", "retry": null},
  ERR_VAL_005: {"title": "Terms not accepted", "status": 400, "severity": "info", "display": "field", "message": "You'll need to accept the Terms of Service and Privacy Policy to create an account.", "action": "Tick the agreement checkbox, then try again.", "retry": null},
  ERR_VAL_006: {"title": "Edit conflict", "status": 409, "severity": "info", "display": "toast", "message": "Someone else changed this just now, so we didn't save your edits to avoid overwriting theirs.", "action": "Refresh to see the latest version, then re-apply your changes.", "retry": null},
  ERR_AUTH_001: {"title": "Invalid credentials", "status": 401, "severity": "info", "display": "field", "message": "That email and password combination didn't match our records.", "action": "Double-check both fields and try again, or use 'Forgot password' to reset it.", "retry": null},
  ERR_AUTH_002: {"title": "Session expired", "status": 401, "severity": "info", "display": "page", "message": "Your session has ended, so we signed you out to keep your account safe.", "action": "Sign in again to pick up where you left off.", "retry": null},
  ERR_AUTH_003: {"title": "Could not verify sign-in", "status": 401, "severity": "warning", "display": "toast", "message": "We couldn't verify your sign-in.", "action": "Refresh the page. If you're still stuck, sign out and back in.", "retry": null},
  ERR_AUTH_004: {"title": "Link invalid or expired", "status": 400, "severity": "info", "display": "page", "message": "This link is no longer valid \u2014 it may have expired or already been used.", "action": "Request a fresh link and use it soon after it arrives.", "retry": null},
  ERR_AUTH_005: {"title": "Email not verified", "status": 403, "severity": "info", "display": "toast", "message": "Confirm your email address before continuing.", "action": "Check your inbox for the verification link, or resend it from your profile.", "retry": null},
  ERR_AUTH_006: {"title": "Account temporarily locked", "status": 429, "severity": "warning", "display": "field", "message": "Too many failed sign-in attempts, so sign-in for this account is paused briefly.", "action": "Wait about 15 minutes and try again, or reset your password now via 'Forgot password'.", "retry": null},
  ERR_AUTH_007: {"title": "Not available while impersonating", "status": 403, "severity": "warning", "display": "toast", "message": "This action isn't available while you're viewing the app as another user.", "action": "End the impersonation session and ask the account owner to do this themselves.", "retry": null},
  ERR_PERM_001: {"title": "Permission denied", "status": 403, "severity": "info", "display": "toast", "message": "You don't have permission to do that in this organization.", "action": "Ask an organization admin to upgrade your role, or switch to an organization where you have access.", "retry": null},
  ERR_PERM_002: {"title": "Not found", "status": 404, "severity": "warning", "display": "toast", "message": "We couldn't find that page or it may have been removed.", "action": "Check the link, or head back to your dashboard.", "retry": null},
  ERR_PERM_003: {"title": "Invitation invalid", "status": 404, "severity": "info", "display": "page", "message": "This invitation is no longer valid.", "action": "Ask the person who invited you to send a new invitation.", "retry": null},
  ERR_PERM_004: {"title": "Administrator access required", "status": 403, "severity": "warning", "display": "page", "message": "This area is for platform administrators.", "action": "Head back to your dashboard. If you believe you should have access, contact an existing administrator.", "retry": null},
  ERR_ORG_001: {"title": "Last owner", "status": 409, "severity": "info", "display": "toast", "message": "An organization needs at least one owner, and this is the only one.", "action": "Make someone else an owner first, then try again.", "retry": null},
  ERR_ORG_002: {"title": "Already a member", "status": 409, "severity": "info", "display": "toast", "message": "That person is already a member of this organization.", "action": "Nothing to do \u2014 they already have access. Check the Members page.", "retry": null},
  ERR_ORG_003: {"title": "Member not found", "status": 404, "severity": "info", "display": "toast", "message": "We couldn't find that member in this organization.", "action": "Refresh the Members page \u2014 they may have already been removed.", "retry": null},
  ERR_ORG_004: {"title": "Organization suspended", "status": 403, "severity": "warning", "display": "page", "message": "This organization has been suspended.", "action": "Contact support to resolve the suspension.", "retry": null},
  ERR_ORG_005: {"title": "Domain not claimable", "status": 400, "severity": "info", "display": "toast", "message": "That domain can't be claimed for this organization.", "action": "Use your company's own domain \u2014 it must match your email address, and shared providers like gmail.com aren't allowed.", "retry": null},
  ERR_ORG_006: {"title": "Domain already claimed", "status": 409, "severity": "info", "display": "toast", "message": "Another organization has already claimed that domain.", "action": "If this is your company's domain, contact support to resolve the conflict.", "retry": null},
  ERR_ORG_007: {"title": "Company workspace already exists", "status": 409, "severity": "info", "display": "field", "message": "Your company already has a workspace.", "action": "Verify your email to join automatically, or ask your company's workspace owner for an invitation.", "retry": null},
  ERR_ADM_001: {"title": "User not found", "status": 404, "severity": "info", "display": "toast", "message": "No user matches that id.", "action": "Refresh the user list \u2014 the account may have been removed.", "retry": null},
  ERR_ADM_002: {"title": "Organization not found", "status": 404, "severity": "info", "display": "toast", "message": "No organization matches that id.", "action": "Refresh the organization list \u2014 it may have been deleted.", "retry": null},
  ERR_ADM_003: {"title": "Cannot deactivate yourself", "status": 409, "severity": "info", "display": "toast", "message": "You can't deactivate your own account from here.", "action": "Ask another administrator to do it, so the platform is never left without an active admin.", "retry": null},
  ERR_ADM_004: {"title": "Error record not found", "status": 404, "severity": "info", "display": "toast", "message": "No error record matches that reference.", "action": "Check the reference for typos \u2014 records also expire after 7 days.", "retry": null},
  ERR_ADM_005: {"title": "Cannot impersonate a superuser", "status": 409, "severity": "warning", "display": "toast", "message": "Superuser accounts can't be impersonated.", "action": "Impersonation is for regular accounts only \u2014 coordinate with the other admin directly.", "retry": null},
  ERR_ADM_006: {"title": "Cannot impersonate a deactivated user", "status": 409, "severity": "info", "display": "toast", "message": "That account is deactivated, so it can't be impersonated.", "action": "Reactivate the account first if you need to see it from the inside.", "retry": null},
  ERR_ADM_007: {"title": "Invitation not found", "status": 404, "severity": "info", "display": "toast", "message": "No pending invitation matches that id.", "action": "Refresh the invitations list \u2014 it may already be accepted or revoked.", "retry": null},
  ERR_ADM_008: {"title": "Invalid merge", "status": 409, "severity": "warning", "display": "toast", "message": "Cannot merge these organizations.", "action": "The target and source organizations must be different, existing organizations.", "retry": null},
  ERR_CRD_001: {"title": "Not enough credits", "status": 409, "severity": "info", "display": "toast", "message": "Your organization doesn't have enough credits for this.", "action": "Buy a credit pack, then try again.", "retry": null, "params": ["required", "available"], "messageSpecific": "This needs {required} credits, but your organization has {available}."},
  ERR_CRD_002: {"title": "Action already settled", "status": 409, "severity": "info", "display": "toast", "message": "That action was already completed or cancelled.", "action": "Refresh to see the current state \u2014 no credits were double-charged.", "retry": null},
  ERR_CRD_003: {"title": "Reservation not found", "status": 404, "severity": "info", "display": "toast", "message": "We couldn't find that pending action.", "action": "Refresh and try again from the start.", "retry": null},
  ERR_CRD_004: {"title": "Unknown action", "status": 409, "severity": "warning", "display": "toast", "message": "That action isn't available.", "action": "Refresh the page \u2014 you may be on an older version of the app.", "retry": null},
  ERR_CRD_005: {"title": "Unknown credit pack", "status": 409, "severity": "warning", "display": "toast", "message": "That credit pack isn't available.", "action": "Refresh the page and pick one of the listed packs.", "retry": null},
  ERR_CRD_006: {"title": "Member credit limit reached", "status": 409, "severity": "info", "display": "toast", "message": "You've reached your monthly credit limit for this organization.", "action": "Ask an organization admin to raise your limit, or try again next month.", "retry": null},
  ERR_CRD_007: {"title": "Not an organization member", "status": 404, "severity": "info", "display": "toast", "message": "That person isn't a member of this organization.", "action": "Check the member list and try again.", "retry": null},
  ERR_GEN_001: {"title": "Generation not found", "status": 404, "severity": "info", "display": "toast", "message": "We couldn't find that generation.", "action": "Head back to your generations list \u2014 it may have been removed.", "retry": null},
  ERR_GEN_002: {"title": "Generation not available", "status": 409, "severity": "warning", "display": "toast", "message": "Content generation isn't set up on this server yet.", "action": "If you run this deployment, configure the provider API keys (see README). Otherwise, contact your administrator.", "retry": null},
  ERR_GEN_003: {"title": "Generation failed", "status": 409, "severity": "error", "display": "toast", "message": "We couldn't finish generating that, and your credits for it have been returned.", "action": "Try again. If it keeps failing, tweak your input or contact support with the code below.", "retry": null},
  ERR_GEN_004: {"title": "Still generating", "status": 409, "severity": "info", "display": "toast", "message": "This is still being generated.", "action": "Give it a few seconds \u2014 the result will appear when it's ready.", "retry": null},
  ERR_GEN_005: {"title": "Can't cancel this", "status": 409, "severity": "info", "display": "toast", "message": "This can only be canceled while it's still generating.", "action": "It already finished \u2014 refresh to see the result.", "retry": null},
  ERR_GEN_006: {"title": "Can't delete this yet", "status": 409, "severity": "info", "display": "toast", "message": "Wait until this finishes before deleting it.", "action": "Cancel it first, then delete it.", "retry": null},
  ERR_PRIV_001: {"title": "Privacy request not found", "status": 404, "severity": "info", "display": "toast", "message": "We couldn't find that privacy request.", "action": "Refresh the queue \u2014 it may have been closed or the link is stale.", "retry": null},
  ERR_PRIV_002: {"title": "Privacy request cannot be updated", "status": 409, "severity": "info", "display": "toast", "message": "That privacy request is not in a state that allows this action.", "action": "Check the current status, then use the next allowed step (verify \u2192 fulfill/forward \u2192 close).", "retry": null},
  ERR_PRIV_003: {"title": "Privacy request incomplete", "status": 400, "severity": "info", "display": "field", "message": "We need a bit more information to process this privacy request.", "action": "Provide a contact email plus an email or phone number for the subject.", "retry": null},
  ERR_LLM_001: {"title": "AI text provider not configured", "status": 409, "severity": "warning", "display": "toast", "message": "This AI text provider isn't set up on this server yet.", "action": "If you run this deployment, add the provider API key (see README). Otherwise, contact your administrator.", "retry": null},
  ERR_LLM_002: {"title": "Text generation failed", "status": 409, "severity": "error", "display": "toast", "message": "The AI provider couldn't complete this request, and your credit for it has been returned.", "action": "Try again. If it keeps failing, switch providers or contact support with the code below.", "retry": null},
  ERR_LLM_003: {"title": "Text completion not found", "status": 404, "severity": "info", "display": "toast", "message": "We couldn't find that text completion.", "action": "Head back to your completions list \u2014 it may have been removed.", "retry": null},
  ERR_BILL_001: {"title": "Billing not configured", "status": 409, "severity": "warning", "display": "toast", "message": "Payments aren't set up on this server yet.", "action": "If you run this deployment, add your Stripe keys (see README). Otherwise, contact your administrator.", "retry": null},
  ERR_BILL_002: {"title": "Payment provider unreachable", "status": 502, "severity": "critical", "display": "toast", "message": "We couldn't reach our payment provider just now. You have not been charged.", "action": "Wait a moment and try again. Your credits and data are unaffected.", "retry": {"afterMs": 2000, "max": 2}},
  ERR_BILL_004: {"title": "No billing account", "status": 409, "severity": "warning", "display": "toast", "message": "This organization doesn't have a billing account yet.", "action": "Buy a credit pack first \u2014 that sets up billing automatically.", "retry": null},
  ERR_BILL_006: {"title": "Credit pack not purchasable", "status": 409, "severity": "warning", "display": "toast", "message": "That credit pack can't be purchased right now.", "action": "Pick another pack, or contact your administrator if none work.", "retry": null},
  ERR_BILL_007: {"title": "Membership plan not available", "status": 409, "severity": "warning", "display": "toast", "message": "That membership plan can't be purchased right now.", "action": "Try the other plan, or contact support if none work.", "retry": null},
  ERR_BILL_008: {"title": "Organization plan not available", "status": 409, "severity": "warning", "display": "toast", "message": "That organization plan can't be purchased right now.", "action": "Choose another plan or contact your administrator.", "retry": null},
  ERR_BILL_009: {"title": "Subscription already active", "status": 409, "severity": "warning", "display": "toast", "message": "This organization already has an active paid subscription.", "action": "Manage your existing plan through the billing portal.", "retry": null},
  ERR_FILE_001: {"title": "File not found", "status": 404, "severity": "warning", "display": "toast", "message": "We couldn't find that file.", "action": "Refresh and try again, or upload the file again if it was removed.", "retry": null},
  ERR_FILE_002: {"title": "Upload too large", "status": 413, "severity": "warning", "display": "toast", "message": "That file is too large to upload.", "action": "Choose a smaller file within the size limit shown.", "retry": null},
  ERR_FILE_003: {"title": "Unsupported file type", "status": 415, "severity": "warning", "display": "toast", "message": "That file type isn't supported.", "action": "Choose a file in one of the supported formats shown.", "retry": null},
  ERR_FILE_004: {"title": "Upload not completed", "status": 409, "severity": "warning", "display": "toast", "message": "Your file upload hasn't completed successfully.", "action": "Wait for the upload to finish, then try again. If it still fails, upload the file again.", "retry": null},
  ERR_FILE_005: {"title": "Storage unavailable", "status": 503, "severity": "error", "display": "toast", "message": "We couldn't reach file storage just now.", "action": "Wait a moment and try again.", "retry": null},
  ERR_FILE_006: {"title": "Upload quota exceeded", "status": 429, "severity": "warning", "display": "toast", "message": "Too many uploaded files.", "action": "Set or remove your current photo, then try again.", "retry": null},
  ERR_ENT_001: {"title": "Plan upgrade required", "status": 403, "severity": "warning", "display": "toast", "message": "Your organization's plan doesn't include this feature.", "action": "Upgrade your organization's plan from Billing to use this feature.", "retry": null},
  ERR_ENT_002: {"title": "Plan limit reached", "status": 403, "severity": "warning", "display": "toast", "message": "Your organization has reached its plan limit.", "action": "Upgrade your organization's plan from Billing for more capacity.", "retry": null, "params": ["limit", "resource"], "messageSpecific": "Your organization has reached its plan limit of {limit} {resource}."},
  ERR_ENT_003: {"title": "Unknown entitlement", "status": 422, "severity": "warning", "display": "toast", "message": "That entitlement isn't recognized.", "action": "Choose a supported entitlement and try again.", "retry": null},
  ERR_SRV_001: {"title": "Internal server error", "status": 500, "severity": "critical", "display": "toast", "message": "Something went wrong on our end. Your data is safe, and we've been notified.", "action": "Try again in a few moments. If it keeps happening, contact support and mention the code shown below.", "retry": null},
  ERR_SRV_002: {"title": "Request timed out", "status": 504, "severity": "error", "display": "toast", "message": "This is taking longer than expected.", "action": "Wait a moment and try again \u2014 your previous attempt may still finish on its own.", "retry": {"afterMs": 2000, "max": 2}},
  ERR_SRV_003: {"title": "Maintenance in progress", "status": 503, "severity": "warning", "display": "page", "message": "We're doing some quick maintenance and will be right back.", "action": "Nothing to fix on your end \u2014 this page will refresh itself when we're done.", "retry": null},
  ERR_SRV_004: {"title": "Duplicate request in progress", "status": 409, "severity": "info", "display": "toast", "message": "We're still working on your previous attempt at this.", "action": "Give it a few seconds \u2014 the first attempt should finish on its own.", "retry": null},
  ERR_KEY_001: {"title": "API key not found", "status": 404, "severity": "info", "display": "toast", "message": "We couldn't find that API key.", "action": "Head back to the API Keys page \u2014 it may have been revoked.", "retry": null},
  ERR_BLOG_001: {"title": "Blog post not found", "status": 404, "severity": "info", "display": "toast", "message": "We couldn't find that blog post.", "action": "Head back to the blog \u2014 it may have been unpublished or removed.", "retry": null},
  ERR_BLOG_002: {"title": "Slug already in use", "status": 409, "severity": "info", "display": "field", "message": "Another post already uses this slug.", "action": "Choose a different slug \u2014 each post needs a unique URL.", "retry": null},
  ERR_BLOG_003: {"title": "Generation job not found", "status": 404, "severity": "info", "display": "toast", "message": "We couldn't find that draft-generation job.", "action": "Head back to the blog admin \u2014 the job may have been cleaned up.", "retry": null},
  ERR_FLAG_001: {"title": "Unknown feature flag", "status": 404, "severity": "info", "display": "toast", "message": "That feature flag doesn't exist.", "action": "Refresh the flags page \u2014 the list of known flags may have changed.", "retry": null},
  ERR_FLAG_002: {"title": "Feature not available", "status": 404, "severity": "info", "display": "toast", "message": "This feature isn't available right now.", "action": "If you followed a link here, the feature may have been turned off \u2014 head back to your dashboard.", "retry": null},
  ERR_COMM_001: {"title": "Profile not found", "status": 404, "severity": "info", "display": "toast", "message": "We couldn't find that community member.", "action": "Head back to the member directory \u2014 they may have left or changed their handle.", "retry": null},
  ERR_COMM_002: {"title": "Handle already taken", "status": 409, "severity": "info", "display": "field", "message": "Someone already uses this handle.", "action": "Pick a different handle \u2014 each member needs a unique one.", "retry": null},
  ERR_COMM_003: {"title": "Not a community member", "status": 403, "severity": "info", "display": "toast", "message": "You need to join the community first.", "action": "Create your community profile, then try again.", "retry": null},
  ERR_COMM_004: {"title": "Premium membership required", "status": 403, "severity": "info", "display": "toast", "message": "Messaging is part of the premium membership.", "action": "Upgrade your community membership to send messages.", "retry": null},
  ERR_COMM_005: {"title": "Community access suspended", "status": 403, "severity": "warning", "display": "toast", "message": "Your community access has been suspended.", "action": "Contact support if you believe this is a mistake.", "retry": null},
  ERR_COMM_006: {"title": "Conversation not found", "status": 404, "severity": "info", "display": "toast", "message": "We couldn't find that conversation.", "action": "Head back to your messages \u2014 the conversation may have been removed.", "retry": null},
  ERR_COMM_007: {"title": "Can't message yourself", "status": 400, "severity": "info", "display": "toast", "message": "You can't start a conversation with yourself.", "action": "Pick another member from the directory.", "retry": null},
  ERR_COMM_009: {"title": "Already a premium member", "status": 409, "severity": "info", "display": "toast", "message": "You already have an active premium membership.", "action": "Manage or cancel it from your membership settings.", "retry": null},
  ERR_COMM_008: {"title": "Member unavailable", "status": 404, "severity": "info", "display": "toast", "message": "That member can't receive messages right now.", "action": "They may have left the community \u2014 try another member.", "retry": null},
  ERR_NET_001: {"title": "You're offline", "status": 0, "severity": "info", "display": "banner", "message": "We can't reach the internet right now.", "action": "Check your connection \u2014 we'll retry automatically, and anything you typed is still here.", "retry": {"afterMs": 1500, "max": 2}},
};

export function isErrorCode(code: string): code is ErrorCode {
  return code in errorCatalog;
}

/** The user-facing headline: the param-specific copy when the server sent
 * every value it needs, otherwise the generic message (never half-filled). */
export function formatErrorMessage(
  entry: Pick<CatalogEntry, "message" | "messageSpecific">,
  params: ErrorParams = {},
): string {
  if (!entry.messageSpecific) return entry.message;
  let complete = true;
  const text = entry.messageSpecific.replace(/\{([a-z_][a-z0-9_]*)\}/g, (_m, name: string) => {
    const value = params[name];
    if (typeof value === "number" && Number.isFinite(value)) return value.toLocaleString();
    if (typeof value === "string" && value.trim()) return value;
    complete = false;
    return "";
  });
  return complete ? text : entry.message;
}
