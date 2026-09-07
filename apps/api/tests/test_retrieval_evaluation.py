"""A regression test for retrieval quality, not just retrieval plumbing.

test_retrieval_and_knowledge_graph.py already checks that search finds
*a* relevant document over an unrelated one. This checks something
harder and more specific: given several documents that are structurally
identical except for one or two distinguishing entity names, does a
differently-worded query naming the right entity actually rank the right
document first? This is the same property `scripts/evaluate_retrieval.py`
measures against real generated data — see
docs/architecture/phase-8-observability-evaluation.md for those numbers.
"""

import uuid

import pytest

from app.models.enterprise import Document, DocumentChunk
from app.services.chunking import chunk_text
from app.services.embeddings import embed
from app.services.retrieval import search_chunks

_TEMPLATE = (
    "Customer mentioned evaluating {competitor} as an alternative during the "
    "quarterly business review. Cited pricing and support response time as "
    "concerns. Usage of {product} has declined noticeably over the last two "
    "quarters."
)

_GROUPS = [
    ("Core Platform", "RivalCo"),
    ("Analytics Suite", "NorthStar Analytics"),
    ("Workflow Engine", "Bravado Systems"),
]


async def _seed_documents(db_session, org_id: uuid.UUID) -> dict[tuple[str, str], uuid.UUID]:
    document_by_group: dict[tuple[str, str], uuid.UUID] = {}
    for product, competitor in _GROUPS:
        content = _TEMPLATE.format(competitor=competitor, product=product)
        document = Document(
            organization_id=org_id, title=f"Notes ({product})", source="crm_note", content=content
        )
        db_session.add(document)
        await db_session.flush()
        for index, chunk in enumerate(chunk_text(content)):
            db_session.add(
                DocumentChunk(
                    organization_id=org_id,
                    document_id=document.id,
                    chunk_index=index,
                    content=chunk,
                    embedding=embed(chunk),
                )
            )
        document_by_group[(product, competitor)] = document.id
    await db_session.commit()
    return document_by_group


@pytest.mark.asyncio
async def test_paraphrased_query_ranks_correct_document_first(db_session) -> None:
    org_id = uuid.uuid4()
    document_by_group = await _seed_documents(db_session, org_id)

    for product, competitor in _GROUPS:
        query = (
            f"Is this account at risk of switching away from {product} in favor "
            f"of {competitor}? Any signs of dissatisfaction?"
        )
        results = await search_chunks(db_session, organization_id=org_id, query=query, top_k=3)
        assert results, f"no results for {product}/{competitor}"
        assert results[0].document_id == document_by_group[(product, competitor)], (
            f"expected the {product}/{competitor} document to rank first"
        )
