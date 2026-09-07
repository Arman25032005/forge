"""Evaluate retrieval quality against real, generated churn-note documents.

This is a genuine, runnable evaluation — it needs no external API or
credentials, unlike the agent/decision evaluation in `evaluate_agent.py`,
because retrieval search (Phase 4) is fully deterministic.

`generate_synthetic_data.py` gives every at-risk customer a CRM note built
from the same template, naming one of a small set of products and
competitors — so many customers end up with *byte-identical* document
content (same product, same competitor). That means "did retrieval find
this exact customer's document" is not a fair question for those
customers: their documents are indistinguishable by content, and any one
of them is an equally correct answer. This evaluates the question
retrieval *can* actually answer: grouping documents by their
(product, competitor) pair, does a differently-worded query naming that
pair retrieve a document from the correct group?

Usage:
    python scripts/evaluate_retrieval.py --org-slug acme
"""

import argparse
import asyncio
import re
from collections import defaultdict

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.enterprise import Document
from app.models.organization import Organization
from app.services.retrieval import search_chunks

_TEMPLATE_RE = re.compile(
    r"evaluating (?P<competitor>.+?) as an alternative.*?Usage of (?P<product>.+?) has declined",
    re.DOTALL,
)


def _extract_group(content: str) -> tuple[str, str] | None:
    match = _TEMPLATE_RE.search(content)
    if match is None:
        return None
    return match.group("product"), match.group("competitor")


def _paraphrased_query(product: str, competitor: str) -> str:
    return (
        f"Is this account at risk of switching away from {product} in favor of "
        f"{competitor}? Any signs of dissatisfaction or reduced engagement?"
    )


async def _get_org(db, org_slug: str) -> Organization:
    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if org is None:
        raise SystemExit(
            f"no organization with slug '{org_slug}' — run generate_synthetic_data.py first"
        )
    return org


async def evaluate(org_slug: str, top_k: int) -> None:
    async with async_session_factory() as db:
        org = await _get_org(db, org_slug)

        result = await db.execute(
            select(Document).where(
                Document.organization_id == org.id, Document.source == "crm_note"
            )
        )
        documents = list(result.scalars().all())
        if not documents:
            raise SystemExit("no CRM note documents found for this organization")

        groups: dict[tuple[str, str], set] = defaultdict(set)
        for document in documents:
            group = _extract_group(document.content)
            if group is not None:
                groups[group].add(document.id)

        if not groups:
            raise SystemExit("could not extract (product, competitor) groups from any document")

        top1_hits = 0
        topk_precisions: list[float] = []

        print(
            f"Organization: {org_slug} — {len(documents)} documents, {len(groups)} distinct "
            f"(product, competitor) groups\n"
        )

        for (product, competitor), doc_ids in sorted(groups.items()):
            query = _paraphrased_query(product, competitor)
            results = await search_chunks(db, organization_id=org.id, query=query, top_k=top_k)

            top1_correct = bool(results) and results[0].document_id in doc_ids
            matches_in_topk = sum(1 for r in results if r.document_id in doc_ids)
            precision = matches_in_topk / len(results) if results else 0.0

            top1_hits += int(top1_correct)
            topk_precisions.append(precision)

            print(
                f"  {product} / {competitor}: {len(doc_ids)} matching docs — "
                f"top-1 correct: {top1_correct}, top-{top_k} precision: {precision:.2f}"
            )

        n = len(groups)
        print(f"\nGroup-level top-1 accuracy: {top1_hits}/{n} = {top1_hits / n:.2%}")
        print(f"Mean top-{top_k} precision:  {sum(topk_precisions) / n:.2%}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org-slug", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(evaluate(args.org_slug, args.top_k))


if __name__ == "__main__":
    main()
