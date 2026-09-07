def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Split text into overlapping, word-boundary-safe chunks.

    Packs whitespace-separated words into chunks of at most `chunk_size`
    characters, then starts the next chunk `overlap` characters back into
    the previous one so a sentence spanning a chunk boundary still appears
    intact in at least one chunk.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    words = text.split()
    if not words:
        return []

    def joined_len(ws: list[str]) -> int:
        return sum(len(w) for w in ws) + max(len(ws) - 1, 0)

    chunks: list[str] = []
    current: list[str] = []

    for word in words:
        candidate = current + [word]
        if current and joined_len(candidate) > chunk_size:
            chunks.append(" ".join(current))
            # Walk backwards from the end of the just-completed chunk to
            # seed the next one with `overlap` characters of context.
            overlap_words: list[str] = []
            for w in reversed(current):
                if joined_len([w, *overlap_words]) > overlap:
                    break
                overlap_words.insert(0, w)
            current = [*overlap_words, word]
        else:
            current = candidate

    if current:
        chunks.append(" ".join(current))

    return chunks
