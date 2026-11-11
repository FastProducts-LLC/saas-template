// GENERATED FILE — do not edit by hand. Source: shared/policy.toml (python3 scripts/gen_policy.py)

// Minimum password length (backend enforcement + registration form feedback).
export const PASSWORD_MIN_LENGTH = 12;

// Prefix on every issued API key; referenced in docs and marketing copy.
export const API_KEY_PREFIX = "sk_live_";

// Days an error reference's full request context is kept in Redis.
export const ERROR_CONTEXT_RETENTION_DAYS = 7;

// Default page size for admin list endpoints.
export const ADMIN_PAGE_SIZE = 25;

// Page size for the credit-ledger history views.
export const CREDIT_HISTORY_PAGE_SIZE = 25;

// Max length: organization name.
export const ORG_NAME_MAX_LENGTH = 120;

// Max length: organization intended-use blurb.
export const ORG_INTENDED_USE_MAX_LENGTH = 500;

// Max length: API key display name.
export const API_KEY_NAME_MAX_LENGTH = 120;

// Max length: admin credit-adjustment note.
export const ADMIN_CREDIT_NOTE_MAX_LENGTH = 255;

// Max length: DSAR intake free-text notes.
export const PRIVACY_REQUEST_NOTES_MAX_LENGTH = 2000;

// Default page size for the public blog list.
export const BLOG_PAGE_SIZE = 10;

// Max length: blog post title.
export const BLOG_TITLE_MAX_LENGTH = 200;

// Max length: blog post slug (also enforced by blog/domain/services.slugify).
export const BLOG_SLUG_MAX_LENGTH = 80;

// Max length: blog post excerpt shown on list cards.
export const BLOG_EXCERPT_MAX_LENGTH = 500;

// Max length: blog post SEO meta title.
export const BLOG_META_TITLE_MAX_LENGTH = 70;

// Max length: blog post SEO meta description.
export const BLOG_META_DESCRIPTION_MAX_LENGTH = 160;

// Max length: blog post cover-image URL.
export const BLOG_COVER_IMAGE_URL_MAX_LENGTH = 500;

// Page size for the community member directory grid.
export const COMMUNITY_DIRECTORY_PAGE_SIZE = 24;

// Page size for a community conversation's message history.
export const COMMUNITY_MESSAGES_PAGE_SIZE = 50;

// Max length: community handle (also enforced by community/domain/services.normalize_handle).
export const COMMUNITY_HANDLE_MAX_LENGTH = 30;

// Max length: community profile display name.
export const COMMUNITY_DISPLAY_NAME_MAX_LENGTH = 80;

// Max length: community profile bio.
export const COMMUNITY_BIO_MAX_LENGTH = 1000;

// Max length: community profile avatar URL.
export const COMMUNITY_AVATAR_URL_MAX_LENGTH = 500;

// Max length: a community direct message body.
export const COMMUNITY_MESSAGE_MAX_LENGTH = 5000;

// Days past current_period_end a past_due subscription keeps premium access.
export const COMMUNITY_PREMIUM_GRACE_DAYS = 3;

// Max length: a single blog post tag.
export const BLOG_TAG_MAX_LENGTH = 40;

// Max number of tags per blog post.
export const BLOG_MAX_TAGS = 5;

// Days a first-party activity event is kept before the daily purge (quoted in the privacy policy).
export const ACTIVITY_EVENT_RETENTION_DAYS = 730;

// Maximum avatar upload size in bytes.
export const UPLOAD_AVATAR_MAX_BYTES = 2097152;
