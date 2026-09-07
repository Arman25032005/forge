"""Generate synthetic enterprise data for one organization.

Creates customers, products, subscriptions, transactions, support tickets,
contracts, invoices, and documents. A configurable fraction of customers are
seeded with a deliberate churn pattern (declining transactions, rising
support tickets, a subscription downgrade, and a document mentioning a
competitor) so that investigation questions like "why did revenue decline"
have a discoverable, non-fabricated answer in the data itself.

Usage:
    python scripts/generate_synthetic_data.py --org-slug acme --customers 200
"""

import argparse
import asyncio
import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.enterprise import (
    Contract,
    Customer,
    Document,
    Invoice,
    Product,
    Subscription,
    SupportTicket,
    Transaction,
)
from app.models.organization import Organization

FIRST_NAMES = ["Acme", "Globex", "Initech", "Umbrella", "Stark", "Wayne", "Hooli", "Vandelay"]
SUFFIXES = ["Corp", "Industries", "Holdings", "Solutions", "Group", "Partners", "Labs"]
PRODUCT_NAMES = ["Core Platform", "Analytics Suite", "Workflow Engine", "Data Connector"]
TICKET_SUBJECTS = [
    "Login issues",
    "Slow performance",
    "Billing question",
    "Feature request",
    "Data export failure",
    "Integration broken",
]
COMPETITOR_NAMES = ["RivalCo", "NorthStar Analytics", "Bravado Systems"]


def _random_company_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(SUFFIXES)} {rng.randint(1, 999)}"


async def _get_or_create_org(db: AsyncSession, slug: str, name: str) -> Organization:
    result = await db.execute(select(Organization).where(Organization.slug == slug))
    org = result.scalar_one_or_none()
    if org is not None:
        return org
    org = Organization(name=name, slug=slug)
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


async def generate(
    *, org_slug: str, org_name: str, customer_count: int, churn_fraction: float, seed: int
) -> None:
    rng = random.Random(seed)
    today = date.today()

    async with async_session_factory() as db:
        org = await _get_or_create_org(db, org_slug, org_name)

        products = [
            Product(organization_id=org.id, name=name, category="saas") for name in PRODUCT_NAMES
        ]
        db.add_all(products)
        await db.commit()

        churn_count = int(customer_count * churn_fraction)
        for i in range(customer_count):
            is_at_risk = i < churn_count
            customer = Customer(
                organization_id=org.id,
                name=_random_company_name(rng),
                segment=rng.choice(["enterprise", "mid-market", "smb"]),
                status="at_risk" if is_at_risk else "active",
            )
            db.add(customer)
            await db.flush()

            product = rng.choice(products)
            start = today - timedelta(days=rng.randint(180, 900))
            subscription = Subscription(
                organization_id=org.id,
                customer_id=customer.id,
                product_id=product.id,
                plan="premium" if not is_at_risk else "standard",
                status="active",
                started_at=start,
            )
            db.add(subscription)

            if is_at_risk:
                # Deliberate pattern: transactions decline over the last 3
                # months relative to the 3 months before that.
                for month_offset in range(6, 0, -1):
                    base_amount = 5000 * (1 - max(0, (6 - month_offset) - 3) * 0.35)
                    amount = round(base_amount * rng.uniform(0.85, 1.15), 2)
                    db.add(
                        Transaction(
                            organization_id=org.id,
                            customer_id=customer.id,
                            amount=max(amount, 100.0),
                            occurred_on=today - timedelta(days=month_offset * 30),
                        )
                    )
                # Elevated support ticket volume in the recent period.
                for _ in range(rng.randint(4, 8)):
                    db.add(
                        SupportTicket(
                            organization_id=org.id,
                            customer_id=customer.id,
                            subject=rng.choice(TICKET_SUBJECTS),
                            severity=rng.choice(["high", "critical"]),
                            opened_on=today - timedelta(days=rng.randint(1, 90)),
                        )
                    )
                # A document mentioning a competitor, discoverable via search.
                competitor = rng.choice(COMPETITOR_NAMES)
                db.add(
                    Document(
                        organization_id=org.id,
                        customer_id=customer.id,
                        title=f"Account notes: {customer.name}",
                        source="crm_note",
                        content=(
                            f"Customer mentioned evaluating {competitor} as an alternative "
                            f"during the quarterly business review. Cited pricing and support "
                            f"response time as concerns. Usage of {product.name} has declined "
                            f"noticeably over the last two quarters."
                        ),
                    )
                )
            else:
                for month_offset in range(6, 0, -1):
                    amount = round(5000 * rng.uniform(0.9, 1.2), 2)
                    db.add(
                        Transaction(
                            organization_id=org.id,
                            customer_id=customer.id,
                            amount=amount,
                            occurred_on=today - timedelta(days=month_offset * 30),
                        )
                    )
                for _ in range(rng.randint(0, 2)):
                    db.add(
                        SupportTicket(
                            organization_id=org.id,
                            customer_id=customer.id,
                            subject=rng.choice(TICKET_SUBJECTS),
                            severity="normal",
                            opened_on=today - timedelta(days=rng.randint(1, 90)),
                        )
                    )

            db.add(
                Contract(
                    organization_id=org.id,
                    customer_id=customer.id,
                    renewal_date=today + timedelta(days=rng.randint(30, 365)),
                    value=round(rng.uniform(10_000, 250_000), 2),
                )
            )
            db.add(
                Invoice(
                    organization_id=org.id,
                    customer_id=customer.id,
                    amount=round(rng.uniform(1_000, 20_000), 2),
                    due_date=today + timedelta(days=rng.randint(-30, 60)),
                    status=rng.choice(["open", "paid", "overdue"]),
                )
            )

            if (i + 1) % 50 == 0:
                await db.commit()

        await db.commit()

    print(
        f"Generated {customer_count} customers ({churn_count} at-risk) "
        f"for organization '{org_slug}' ({org.id})."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org-slug", default="demo-org")
    parser.add_argument("--org-name", default="Demo Organization")
    parser.add_argument("--customers", type=int, default=200)
    parser.add_argument("--churn-fraction", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    asyncio.run(
        generate(
            org_slug=args.org_slug,
            org_name=args.org_name,
            customer_count=args.customers,
            churn_fraction=args.churn_fraction,
            seed=args.seed,
        )
    )


if __name__ == "__main__":
    main()
