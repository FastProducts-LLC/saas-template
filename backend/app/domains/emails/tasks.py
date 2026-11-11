"""Emails worker wiring.

No tasks of its own: this module exists so Celery autodiscovery imports it in
every worker, which installs the suppression lookup that `send_email_task`
consults before each send (see `app/core/email/suppression.py`).
"""

from app.core.email.suppression import register_suppression_check
from app.domains.emails.worker import is_address_suppressed

register_suppression_check(is_address_suppressed)
