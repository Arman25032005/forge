import pytest

from app.services.chunking import chunk_text


def test_empty_text_produces_no_chunks() -> None:
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_short_text_produces_single_chunk() -> None:
    chunks = chunk_text("the quick brown fox", chunk_size=100, overlap=10)
    assert chunks == ["the quick brown fox"]


def test_long_text_splits_into_multiple_chunks_within_size() -> None:
    text = " ".join(f"word{i}" for i in range(200))
    chunks = chunk_text(text, chunk_size=50, overlap=10)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 50


def test_consecutive_chunks_overlap() -> None:
    text = " ".join(f"word{i}" for i in range(50))
    chunks = chunk_text(text, chunk_size=40, overlap=15)
    assert len(chunks) > 1
    for first, second in zip(chunks, chunks[1:], strict=False):
        first_words = first.split()
        second_words = second.split()
        assert first_words[-1] in second_words[: len(second_words) // 2 + 1]


def test_no_content_is_dropped() -> None:
    words = [f"word{i}" for i in range(100)]
    text = " ".join(words)
    chunks = chunk_text(text, chunk_size=60, overlap=10)
    seen = set()
    for chunk in chunks:
        seen.update(chunk.split())
    assert seen == set(words)


def test_overlap_must_be_smaller_than_chunk_size() -> None:
    with pytest.raises(ValueError):
        chunk_text("some text here", chunk_size=10, overlap=10)
