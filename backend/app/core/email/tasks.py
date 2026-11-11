"""Celery tasks for async email delivery and marketing-list sync.

All transactional emails are dispatched through ``send_email_task`` on the
``default`` queue. The task is idempotent (sending the same email twice is
harmless) and retries with exponential backoff on transient provider errors.
Suppressed addresses (hard bounce / spam complaint) are dropped here, so the
rule holds for every slice's mailer.

Marketing-list sync (subscribe/unsubscribe/delete) goes through
``marketing_sync_task`` on the same queue — the provider calls are idempotent
(subscribing twice / deleting a missing contact is a no-op upsert), so
redelivery and retries are safe.
"""

import logging

from celery import shared_task

from app.core.celery_app import run_async

logger = logging.getLogger(__name__)


@shared_task(
    name="app.core.email.tasks.send_email_task",
    queue="default",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
)
def send_email_task(
    self,
    *,
    to: str,
    subject: str,
    text: str | None = None,
    html: str | None = None,
    tags: dict[str, str] | None = None,
) -> None:
    run_async(_send(to=to, subject=subject, text=text, html=html, tags=tags))


async def _send(
    *, to: str, subject: str, text: str | None, html: str | None, tags: dict[str, str] | None
) -> None:
    from app.core.email import get_provider
    from app.core.email.suppression import is_suppressed

    # The one chokepoint every mailer goes through: bounced / complained
    # addresses get nothing, whichever slice asked for the send.
    if await is_suppressed(to):
        logger.info("Skipping email to suppressed address %s (subject=%r)", to, subject)
        return
    await get_provider().send_email(to=to, subject=subject, text=text, html=html, tags=tags)


@shared_task(
    name="app.core.email.tasks.marketing_sync_task",
    queue="default",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
)
def marketing_sync_task(
    self, *, action: str, email: str, first_name: str = "", last_name: str = ""
) -> None:
    run_async(
        _marketing_sync(action=action, email=email, first_name=first_name, last_name=last_name)
    )


async def _marketing_sync(*, action: str, email: str, first_name: str, last_name: str) -> None:
    from app.core.email import get_provider

    provider = get_provider()
    if action == "subscribe":
        await provider.subscribe_to_marketing(
            email=email, first_name=first_name, last_name=last_name
        )
    elif action == "unsubscribe":
        await provider.unsubscribe_from_marketing(email=email)
    elif action == "delete":
        await provider.delete_contact(email=email)
    else:  # bad enqueue is a bug — surface it (retries are harmless)
        raise ValueError(f"Unknown marketing sync action: {action!r}")
