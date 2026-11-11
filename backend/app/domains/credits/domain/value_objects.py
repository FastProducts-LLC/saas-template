"""Credits value objects and catalogs.

These are pure domain concepts shared by credits, billing, generations, and
LLM use cases. They carry no persistence or framework dependencies.
"""

import enum
from dataclasses import dataclass
from datetime import timedelta


class CreditAction(str, enum.Enum):
    """Metered actions a reservation can be opened for."""

    IMAGE_NANO_BANANA = "image_nano_banana"  # Gemini nano-banana image generation
    IMAGE_GPT = "image_gpt"  # OpenAI GPT image generation
    VIDEO_VEO = "video_veo"  # VEO 3.1 video generation
    LLM_CALL = "llm_call"  # generic text LLM call (Gemini / GPT / Anthropic)


@dataclass(frozen=True)
class ActionSpec:
    action: CreditAction
    name: str
    cost: int
    hold_ttl: timedelta  # how long a pending hold stays valid


ACTIONS: dict[CreditAction, ActionSpec] = {
    CreditAction.IMAGE_NANO_BANANA: ActionSpec(
        CreditAction.IMAGE_NANO_BANANA,
        "Image (Nano Banana)",
        cost=5,
        hold_ttl=timedelta(minutes=30),
    ),
    CreditAction.IMAGE_GPT: ActionSpec(
        CreditAction.IMAGE_GPT, "Image (GPT)", cost=5, hold_ttl=timedelta(minutes=30)
    ),
    CreditAction.VIDEO_VEO: ActionSpec(
        CreditAction.VIDEO_VEO, "Video (VEO 3.1)", cost=50, hold_ttl=timedelta(hours=2)
    ),
    CreditAction.LLM_CALL: ActionSpec(
        CreditAction.LLM_CALL, "LLM call", cost=1, hold_ttl=timedelta(minutes=15)
    ),
}

# Credits granted to every org on the first wallet touch of each calendar
# month. Zero: no free monthly credits — metered actions require purchased
# packs. Raise this to give every org a free-tier allowance.
MONTHLY_ALLOWANCE_CREDITS = 0

# Fraction of the monthly allowance below which the org owners get a
# low-balance heads-up (once per allowance period).
LOW_BALANCE_FRACTION = 0.2


class CreditPack(str, enum.Enum):
    """One-time top-up packs purchasable via Stripe (mode=payment)."""

    STARTER = "starter"  # $25
    GROWTH = "growth"  # $50
    SCALE = "scale"  # $100
    BULK = "bulk"  # $200


@dataclass(frozen=True)
class CreditPackSpec:
    pack: CreditPack
    name: str
    credits: int
    price_cents: int

    @property
    def unit_price_cents(self) -> int:
        return round(self.price_cents / self.credits)

    @property
    def discount_pct(self) -> int:
        """Volume discount vs the most expensive per-credit pack in the catalog."""
        base = max(s.price_cents / s.credits for s in CREDIT_PACKS.values())
        return round(100 * (1 - (self.price_cents / self.credits) / base))


# Stripe price ids resolve in the billing gateway (settings), keeping this
# catalog pure; tune credits/price per project — unit price and discount
# derive from them.
CREDIT_PACKS: dict[CreditPack, CreditPackSpec] = {
    CreditPack.STARTER: CreditPackSpec(CreditPack.STARTER, "Starter", credits=50, price_cents=2500),
    CreditPack.GROWTH: CreditPackSpec(CreditPack.GROWTH, "Growth", credits=100, price_cents=5000),
    CreditPack.SCALE: CreditPackSpec(CreditPack.SCALE, "Scale", credits=200, price_cents=10000),
    CreditPack.BULK: CreditPackSpec(CreditPack.BULK, "Bulk", credits=450, price_cents=20000),
}


class ReservationStatus(str, enum.Enum):
    PENDING = "pending"
    CAPTURED = "captured"
    RELEASED = "released"
    EXPIRED = "expired"


class TransactionType(str, enum.Enum):
    GRANT = "grant"  # credits added (monthly allowance, admin grant)
    HOLD = "hold"  # reservation opened: available balance deducted
    RELEASE = "release"  # reservation released on failure: hold refunded
    EXPIRE = "expire"  # reservation expired unclaimed: hold refunded
    ADJUSTMENT = "adjustment"  # manual correction / late capture after expiry
