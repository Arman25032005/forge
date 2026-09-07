import math

from app.services.embeddings import DIMENSIONS, cosine_similarity, embed


def test_embed_is_deterministic() -> None:
    assert embed("the customer churned last month") == embed("the customer churned last month")


def test_embed_returns_expected_dimensionality() -> None:
    assert len(embed("hello world")) == DIMENSIONS


def test_embed_is_unit_normalized() -> None:
    vector = embed("some reasonably long piece of text about invoices and contracts")
    norm = math.sqrt(sum(v * v for v in vector))
    assert math.isclose(norm, 1.0, abs_tol=1e-9)


def test_empty_text_embeds_to_zero_vector() -> None:
    assert embed("") == [0.0] * DIMENSIONS


def test_shared_vocabulary_scores_higher_than_unrelated_text() -> None:
    query = embed("customer churn risk declining transactions")
    related = embed("this customer shows declining transaction volume and churn risk")
    unrelated = embed("the quarterly office holiday party schedule was updated")

    assert cosine_similarity(query, related) > cosine_similarity(query, unrelated)


def test_identical_text_has_similarity_one() -> None:
    vector = embed("invoice overdue by thirty days")
    assert math.isclose(cosine_similarity(vector, vector), 1.0, abs_tol=1e-9)
