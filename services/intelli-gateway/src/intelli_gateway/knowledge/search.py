"""Keyword search over experience notes. Pure function, no I/O."""

from collections.abc import Sequence

from intelli_gateway.schemas.knowledge import KnowledgeDocument, KnowledgeKind


def search_notes(
    documents: Sequence[KnowledgeDocument],
    keywords: Sequence[str],
    limit: int,
    device_id: int | None = None,
) -> list[KnowledgeDocument]:
    """Experience notes matching any keyword (title, text, linked point names), best match
    first (most keyword hits, then title). With device_id: only notes about that device."""
    terms = [keyword.lower() for keyword in keywords if keyword.strip()]
    scored: list[tuple[int, KnowledgeDocument]] = []
    for document in documents:
        if document.kind is not KnowledgeKind.EXPERIENCE_NOTE:
            continue
        if device_id is not None and document.device_id != device_id:
            continue
        haystack = "\n".join([document.title, document.body, *document.point_names]).lower()
        score = sum(haystack.count(term) for term in terms)
        if score:
            scored.append((score, document))
    scored.sort(key=lambda pair: (-pair[0], pair[1].title))
    return [document for _, document in scored[:limit]]
