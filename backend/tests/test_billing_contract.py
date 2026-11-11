"""Billing/credits contract tests.

The drift these catch: the credit-pack catalog and the Stripe wiring are
declared in different places — `CREDIT_PACKS` in the credits domain, the
`stripe_price_credits_<pack>` ids in Settings — and the gateway resolves the
settings field by naming convention (`getattr`, defaulting to ""). Renaming or
adding a pack without touching config.py silently produces an unpurchasable
pack; these tests make that loud.

Price *amounts* live on the Stripe Price objects and can't be asserted
offline — `python scripts/stripe_sync.py --check` reconciles the catalog
against Stripe (run it after editing CREDIT_PACKS or Stripe prices).
"""

from app.core.config import settings
from app.domains.credits.domain.value_objects import ACTIONS, CREDIT_PACKS, CreditAction, CreditPack


def test_every_credit_pack_has_a_stripe_price_setting():
    missing = [
        pack.value
        for pack in CreditPack
        if not hasattr(settings, f"stripe_price_credits_{pack.value}")
    ]
    assert not missing, (
        f"Settings has no stripe_price_credits_* field for pack(s): {missing}. "
        "The billing gateway resolves price ids by naming convention — add the "
        "field to app/core/config.py (and the .env examples) or the pack can "
        "never be purchased."
    )


def test_credit_pack_catalog_covers_every_pack():
    assert set(CREDIT_PACKS) == set(CreditPack), (
        "CREDIT_PACKS must have a spec for every CreditPack member — a pack "
        "without a spec crashes checkout when Stripe reports the purchase."
    )


def test_action_catalog_covers_every_action():
    assert set(ACTIONS) == set(CreditAction), (
        "ACTIONS must have a spec for every CreditAction member — an action "
        "without a cost cannot be reserved."
    )
