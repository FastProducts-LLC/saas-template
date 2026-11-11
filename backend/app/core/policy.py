"""GENERATED FILE — do not edit by hand.

Source: shared/policy.toml (python3 scripts/gen_policy.py)
"""

# Minimum password length (backend enforcement + registration form feedback).
PASSWORD_MIN_LENGTH = 12

# Prefix on every issued API key; referenced in docs and marketing copy.
API_KEY_PREFIX = "sk_live_"

# Days an error reference's full request context is kept in Redis.
ERROR_CONTEXT_RETENTION_DAYS = 7

# Default page size for admin list endpoints.
ADMIN_PAGE_SIZE = 25

# Page size for the credit-ledger history views.
CREDIT_HISTORY_PAGE_SIZE = 25

# Max length: organization name.
ORG_NAME_MAX_LENGTH = 120

# Max length: organization intended-use blurb.
ORG_INTENDED_USE_MAX_LENGTH = 500

# Max length: API key display name.
API_KEY_NAME_MAX_LENGTH = 120

# Max length: admin credit-adjustment note.
ADMIN_CREDIT_NOTE_MAX_LENGTH = 255

# Max length: DSAR intake free-text notes.
PRIVACY_REQUEST_NOTES_MAX_LENGTH = 2000

# Default page size for the public blog list.
BLOG_PAGE_SIZE = 10

# Max length: blog post title.
BLOG_TITLE_MAX_LENGTH = 200

# Max length: blog post slug (also enforced by blog/domain/services.slugify).
BLOG_SLUG_MAX_LENGTH = 80

# Max length: blog post excerpt shown on list cards.
BLOG_EXCERPT_MAX_LENGTH = 500

# Max length: blog post SEO meta title.
BLOG_META_TITLE_MAX_LENGTH = 70

# Max length: blog post SEO meta description.
BLOG_META_DESCRIPTION_MAX_LENGTH = 160

# Max length: blog post cover-image URL.
BLOG_COVER_IMAGE_URL_MAX_LENGTH = 500

# Page size for the community member directory grid.
COMMUNITY_DIRECTORY_PAGE_SIZE = 24

# Page size for a community conversation's message history.
COMMUNITY_MESSAGES_PAGE_SIZE = 50

# Max length: community handle (also enforced by community/domain/services.normalize_handle).
COMMUNITY_HANDLE_MAX_LENGTH = 30

# Max length: community profile display name.
COMMUNITY_DISPLAY_NAME_MAX_LENGTH = 80

# Max length: community profile bio.
COMMUNITY_BIO_MAX_LENGTH = 1000

# Max length: community profile avatar URL.
COMMUNITY_AVATAR_URL_MAX_LENGTH = 500

# Max length: a community direct message body.
COMMUNITY_MESSAGE_MAX_LENGTH = 5000

# Days past current_period_end a past_due subscription keeps premium access.
COMMUNITY_PREMIUM_GRACE_DAYS = 3

# Max length: a single blog post tag.
BLOG_TAG_MAX_LENGTH = 40

# Max number of tags per blog post.
BLOG_MAX_TAGS = 5

# Request limit per client IP: auth register.
RATE_LIMIT_AUTH_REGISTER = "10/hour"

# Request limit per client IP: auth login.
RATE_LIMIT_AUTH_LOGIN = "5/minute"

# Request limit per client IP: auth refresh.
RATE_LIMIT_AUTH_REFRESH = "30/minute"

# Request limit per client IP: auth forgot password.
RATE_LIMIT_AUTH_FORGOT_PASSWORD = "5/hour"

# Request limit per client IP: auth reset password.
RATE_LIMIT_AUTH_RESET_PASSWORD = "10/hour"

# Request limit per client IP: auth verify email.
RATE_LIMIT_AUTH_VERIFY_EMAIL = "30/hour"

# Request limit per client IP: auth resend verification.
RATE_LIMIT_AUTH_RESEND_VERIFICATION = "5/hour"

# Request limit per client IP: auth change password.
RATE_LIMIT_AUTH_CHANGE_PASSWORD = "5/hour"

# Request limit per client IP: community start conversation.
RATE_LIMIT_COMMUNITY_START_CONVERSATION = "30/minute"

# Request limit per client IP: community send message.
RATE_LIMIT_COMMUNITY_SEND_MESSAGE = "30/minute"

# Request limit per client IP: generations create.
RATE_LIMIT_GENERATIONS_CREATE = "20/minute"

# Request limit per client IP: llm complete.
RATE_LIMIT_LLM_COMPLETE = "60/minute"

# Request limit per client IP: privacy request submit.
RATE_LIMIT_PRIVACY_REQUEST_SUBMIT = "5/minute"

# Request limit per client IP: file upload creation.
RATE_LIMIT_FILES_UPLOAD = "30/hour"

# Days a first-party activity event is kept before the daily purge (quoted in the privacy policy).
ACTIVITY_EVENT_RETENTION_DAYS = 730

# Maximum avatar upload size in bytes.
UPLOAD_AVATAR_MAX_BYTES = 2097152

# Maximum confirmed avatar files per user.
UPLOAD_AVATAR_MAX_FILES = 5

# Lifetime of presigned upload and download URLs in seconds.
UPLOAD_PRESIGN_TTL_SECONDS = 300

# Age in hours after which unconfirmed uploads are deleted.
UPLOAD_PENDING_TTL_HOURS = 24

# Days past current_period_end a past_due organization plan keeps paid access.
BILLING_PLAN_GRACE_DAYS = 3

# Trial duration for plan checkout; zero disables trials.
BILLING_TRIAL_DAYS = 0
