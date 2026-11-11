"""Dev seed: a ready-to-use superuser + org + credits, in one command.

    docker compose exec backend python scripts/seed_dev.py

Idempotent — safe to re-run; it tops the org back up to the seed balance but
never duplicates the user or organization. DEV ONLY: refuses to run unless
this is a local dev stack (not production, every configured URL local).

The superuser password is NOT a committed constant — the template is public
and the dev API port is published on the LAN. It is generated once per
checkout and stored in backend/.dev-secrets/seed_password (gitignored); every
run prints it. Set SEED_DEV_PASSWORD to choose your own. Demo members get
throwaway random passwords: reach them via Platform Admin -> impersonate.
Accounts seeded by older versions with the shared password are rotated.

Seeds:
  user      dev@example.com / <generated>   (email-verified superuser)
  org       "Dev Org" (owner)
  wallet    500 credits
  community flag ON + 3 demo members (one premium, no Stripe needed) + a
            seeded DM conversation with the dev user
"""

import asyncio
import os
import secrets
import sys
from pathlib import Path

# Runnable as `python scripts/seed_dev.py` from /app without installing the
# package: put the backend root on sys.path before the app imports.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

# Imperative mappings register on orm-module import — required before the
# domain entities can be used in queries here.
import app.domains.community.infrastructure.orm  # noqa: E402, F401
import app.domains.feature_flags.infrastructure.orm  # noqa: E402, F401
from app.core import dev_secrets  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.domains.auth.domain import User  # noqa: E402
from app.domains.auth.infrastructure.security import Argon2PasswordHasher  # noqa: E402
from app.domains.community.domain import (  # noqa: E402
    CommunityMembership,
    CommunityProfile,
    Conversation,
    ConversationParticipant,
    Message,
    SubscriptionStatus,
)
from app.domains.community.domain.services import dm_key  # noqa: E402
from app.domains.credits.domain import CreditWallet  # noqa: E402
from app.domains.credits.interface.deps import build_credit_engine  # noqa: E402
from app.domains.feature_flags.domain import FeatureFlag  # noqa: E402
from app.domains.organizations.domain import (  # noqa: E402
    Membership,
    Organization,
    Role,
    slugify,
)

EMAIL = "dev@example.com"
# The password every seeded account shared before it became per-checkout;
# only used to detect and rotate those accounts.
LEGACY_PASSWORD = "Dev_password1"  # noqa: S105
ORG_NAME = "Dev Org"
SEED_CREDITS = 500


def _random_password() -> str:
    return f"Dev_{secrets.token_urlsafe(12)}1"


def dev_password() -> str:
    return os.environ.get("SEED_DEV_PASSWORD") or dev_secrets.load_or_create(
        "seed_password", _random_password
    )


async def seed() -> None:
    if not settings.is_local_dev:
        sys.exit(
            "Refusing to seed: not a local dev stack (ENVIRONMENT=production, or "
            "FRONTEND_URL/CORS_ORIGINS point at a non-local host). This creates a "
            "superuser."
        )
    password = dev_password()
    hasher = Argon2PasswordHasher()

    async with SessionLocal() as db:
        async with db.begin():
            user = (await db.execute(select(User).where(User.email == EMAIL))).scalar_one_or_none()
            if user is None:
                user = User.register(
                    email=EMAIL,
                    password_hash=hasher.hash(password),
                    first_name="Dev",
                    last_name="User",
                    marketing_opt_in=False,
                )
                user.mark_email_verified()
                db.add(user)
                await db.flush()
                print(f"created user   {EMAIL}")
            elif hasher.verify(LEGACY_PASSWORD, user.password_hash):
                user.change_password(hasher.hash(password))
                print(f"rotated user   {EMAIL} (was the old shared seed password)")
            elif os.environ.get("SEED_DEV_PASSWORD") and not hasher.verify(
                password, user.password_hash
            ):
                user.change_password(hasher.hash(password))
                print(f"updated user   {EMAIL} (SEED_DEV_PASSWORD)")
            else:
                print(f"exists  user   {EMAIL}")
            user.is_superuser = True

            # Look up by slug (the unique column) so a rerun can never collide
            # with an existing org that happens to slugify the same way.
            slug = slugify(ORG_NAME)
            org = (
                await db.execute(select(Organization).where(Organization.slug == slug))
            ).scalar_one_or_none()
            if org is None:
                org = Organization(name=ORG_NAME, slug=slug)
                db.add(org)
                await db.flush()
                print(f"created org    {ORG_NAME}")
            else:
                print(f"exists  org    {org.name} ({slug})")

            # Ensure the dev user owns the org even if either side pre-existed
            # (e.g. the user was deleted and re-seeded against a surviving org).
            membership = (
                await db.execute(
                    select(Membership).where(
                        Membership.organization_id == org.id,
                        Membership.user_id == user.id,
                    )
                )
            ).scalar_one_or_none()
            if membership is None:
                db.add(Membership(organization_id=org.id, user_id=user.id, role=Role.OWNER))
                print("linked  owner  membership")

            wallet = (
                await db.execute(select(CreditWallet).where(CreditWallet.organization_id == org.id))
            ).scalar_one_or_none()
            balance = wallet.balance if wallet else 0
            if balance < SEED_CREDITS:
                await build_credit_engine(db).grant(
                    org.id,
                    SEED_CREDITS - balance,
                    "Dev seed",
                    idempotency_key=None,
                )
                granted = SEED_CREDITS - balance
                print(f"granted        {granted} credits (balance -> {SEED_CREDITS})")
            else:
                print(f"exists  wallet {balance} credits")

            await seed_community(db, user)

    print(f"\nSeeded. Sign in at the frontend as {EMAIL} / {password}")
    if not os.environ.get("SEED_DEV_PASSWORD"):
        print("(unique to this checkout — stored in backend/.dev-secrets/seed_password;")
        print(" if you changed the password in the app, that file is stale.)")
    print("The Platform Admin link appears in the sidebar (superuser), and")
    print("Community is enabled with demo members + a conversation. Demo members")
    print("have no known password: impersonate them from Platform Admin.")


# (handle, display name, bio, premium?)
COMMUNITY_MEMBERS = [
    ("dev", "Dev User", "Superuser test account.", False),
    ("ada_l", "Ada Lovelace", "First programmer. Ask me about engines.", True),
    ("grace_h", "Grace Hopper", "Compilers and clocks.", False),
    ("alan_t", "Alan Turing", "Machines that think.", False),
]


async def seed_community(db, dev_user: User) -> None:
    """Flag on + demo profiles (one premium, no Stripe) + one conversation."""
    flag = (
        await db.execute(select(FeatureFlag).where(FeatureFlag.key == "community"))
    ).scalar_one_or_none()
    if flag is None:
        db.add(FeatureFlag(key="community", enabled=True))
        print("enabled        community flag")
    elif not flag.enabled:
        flag.enabled = True
        print("enabled        community flag")
    else:
        print("exists  flag   community (on)")

    hasher = Argon2PasswordHasher()
    users_by_handle: dict[str, User] = {}
    for handle, display_name, bio, premium in COMMUNITY_MEMBERS:
        if handle == "dev":
            member_user = dev_user
        else:
            email = f"{handle}@example.com"
            member_user = (
                await db.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if member_user is None:
                member_user = User.register(
                    email=email,
                    # Nobody signs in as a demo member directly.
                    password_hash=hasher.hash(_random_password()),
                    first_name=display_name.split()[0],
                    last_name=display_name.split()[-1],
                    marketing_opt_in=False,
                )
                member_user.mark_email_verified()
                db.add(member_user)
                await db.flush()
            elif hasher.verify(LEGACY_PASSWORD, member_user.password_hash):
                member_user.change_password(hasher.hash(_random_password()))
                print(f"rotated member @{handle} (was the old shared seed password)")
        users_by_handle[handle] = member_user

        profile = (
            await db.execute(
                select(CommunityProfile).where(CommunityProfile.user_id == member_user.id)
            )
        ).scalar_one_or_none()
        if profile is None:
            db.add(
                CommunityProfile(
                    user_id=member_user.id,
                    handle=handle,
                    display_name=display_name,
                    bio=bio,
                )
            )
            membership = CommunityMembership(user_id=member_user.id)
            if premium:
                # Direct row fields — no Stripe needed in dev.
                membership.apply_subscription(
                    subscription_id=f"sub_seed_{handle}",
                    status=SubscriptionStatus.ACTIVE,
                    current_period_end=None,
                    cancel_at_period_end=False,
                    customer_id=f"cus_seed_{handle}",
                )
            db.add(membership)
            await db.flush()
            print(f"created member @{handle}{' (premium)' if premium else ''}")
        else:
            print(f"exists  member @{handle}")

    # One conversation: ada (premium) -> dev, so Messages isn't empty.
    ada, dev = users_by_handle["ada_l"], users_by_handle["dev"]
    key = dm_key(ada.id, dev.id)
    conversation = (
        await db.execute(select(Conversation).where(Conversation.dm_key == key))
    ).scalar_one_or_none()
    if conversation is None:
        conversation = Conversation(dm_key=key, created_by=ada.id)
        db.add(conversation)
        await db.flush()
        for uid in (ada.id, dev.id):
            db.add(ConversationParticipant(conversation_id=conversation.id, user_id=uid))
        message = Message(
            conversation_id=conversation.id,
            body="Welcome to the community! This thread was seeded by scripts/seed_dev.py.",
            sender_id=ada.id,
        )
        db.add(message)
        await db.flush()
        conversation.last_message_at = message.created_at
        print("created demo conversation (@ada_l -> @dev)")
    else:
        print("exists  demo conversation")


if __name__ == "__main__":
    asyncio.run(seed())
