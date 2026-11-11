"""Compare local organization subscriptions with Stripe without writing either side."""

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path


async def reconcile():
    from app.core.database import SessionLocal, engine
    from app.domains.billing.infrastructure.stripe_gateway import StripeGateway
    from app.domains.billing.interface.deps import build_reconcile_revenue

    try:
        async with SessionLocal() as session:
            return await build_reconcile_revenue(session, StripeGateway()).execute()
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.core.config import settings

    if not settings.stripe_secret_key:
        print("STRIPE_SECRET_KEY is not set — cannot reconcile revenue.", file=sys.stderr)
        return 2
    report = asyncio.run(reconcile())
    if args.json:
        print(json.dumps(asdict(report), default=str))
    else:
        print("Revenue in sync" if report.in_sync else "Revenue drift detected")
        print(f"MRR (cents): local={report.local_mrr_cents}, Stripe={report.stripe_mrr_cents}")
        for item in report.drift:
            print(
                f"  {item.kind}: subscription={item.subscription_id}, org={item.org_id} "
                f"local={item.local_value} Stripe={item.stripe_value}"
            )
    return 0 if report.in_sync else 1


if __name__ == "__main__":
    sys.exit(main())
