"""Build one site's knowledge text (sent in full in the system prompt) and track its size.

v1 has no search/RAG: the whole text goes into a cached system block. Its token size is logged
per site; above KNOWLEDGE_TOKEN_WARN a warning is logged, the signal to add search later.
"""

import hashlib
import logging
from dataclasses import dataclass

from intelli_gateway.interfaces.knowledge_store import KnowledgeStore
from intelli_gateway.interfaces.llm_client import TokenCounter
from intelli_gateway.schemas.knowledge import KnowledgeDocument, KnowledgeKind

logger = logging.getLogger(__name__)

_SECTION_TITLES = {
    KnowledgeKind.MANUAL: "Manuals",
    KnowledgeKind.IM_SCRIPT: "Device information model (IM) scripts",
    KnowledgeKind.EXPERIENCE_NOTE: "Engineers' experience notes",
}


@dataclass(frozen=True)
class SiteKnowledge:
    site_id: int
    text: str
    version: str
    token_count: int
    token_count_exact: bool


def render_knowledge(documents: list[KnowledgeDocument]) -> str:
    """Deterministic text (stable order, no timestamps of the request) so the prompt cache hits."""
    sections: list[str] = []
    for kind, heading in _SECTION_TITLES.items():
        docs = sorted(
            (document for document in documents if document.kind is kind),
            key=lambda document: (document.device_id or 0, document.title),
        )
        if not docs:
            continue
        parts = [f"## {heading}"]
        for document in docs:
            meta = [f"updated {document.updated_at.date().isoformat()}"]
            if document.device_id is not None:
                meta.insert(0, f"device_id {document.device_id}")
            if document.author:
                meta.append(f"by {document.author}")
            parts.append(f"### {document.title} ({', '.join(meta)})\n{document.body}")
        sections.append("\n\n".join(parts))
    return "\n\n".join(sections) if sections else "(no knowledge documents for this site)"


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class KnowledgeLoader:
    def __init__(self, store: KnowledgeStore, counter: TokenCounter, warn_threshold: int) -> None:
        self._store = store
        self._counter = counter
        self._warn_threshold = warn_threshold
        self._token_counts: dict[tuple[int, str], tuple[int, bool]] = {}

    async def load(self, site_id: int) -> SiteKnowledge:
        text = render_knowledge(await self._store.list_documents(site_id))
        version = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        key = (site_id, version)
        if key not in self._token_counts:
            counted = await self._counter.count_tokens(text)
            exact = counted is not None
            tokens = counted if counted is not None else estimate_tokens(text)
            self._token_counts[key] = (tokens, exact)
            fields: dict[str, object] = {
                "site_id": site_id,
                "knowledge_version": version,
                "knowledge_tokens": tokens,
                "exact": exact,
                "threshold": self._warn_threshold,
            }
            if tokens > self._warn_threshold:
                logger.warning("site_knowledge_over_threshold", extra={"fields": fields})
            else:
                logger.info("site_knowledge_size", extra={"fields": fields})
        tokens, exact = self._token_counts[key]
        return SiteKnowledge(
            site_id=site_id, text=text, version=version, token_count=tokens, token_count_exact=exact
        )
