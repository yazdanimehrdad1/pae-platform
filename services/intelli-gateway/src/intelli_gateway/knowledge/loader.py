"""Build one site's knowledge text (sent in full in the system prompt) and track its size.

v1 has no search/RAG: the whole text goes into a cached system block. Its token size is logged
per site; above KNOWLEDGE_TOKEN_WARN a warning is logged, the signal to add search later.
"""

import hashlib
import logging
from dataclasses import dataclass

from intelli_gateway.interfaces.knowledge_store import KnowledgeStore
from intelli_gateway.interfaces.llm_client import TokenCounter
from intelli_gateway.schemas.knowledge import (
    DeviceFacts,
    KnowledgeDocument,
    KnowledgeKind,
    SitePrompt,
)

logger = logging.getLogger(__name__)

_SECTION_TITLES = {
    KnowledgeKind.MANUAL: "Manuals",
    KnowledgeKind.IM_SCRIPT: "Device information model (IM) scripts",
    KnowledgeKind.PROCEDURE: "Procedures",
    KnowledgeKind.EXPERIENCE_NOTE: "Engineers' experience notes",
}


@dataclass(frozen=True)
class SiteKnowledge:
    site_id: int
    text: str
    version: str
    token_count: int
    token_count_exact: bool


def _render_facts(facts: list[DeviceFacts]) -> str | None:
    if not facts:
        return None
    parts = ["## Device ratings and notes"]
    for entry in sorted(facts, key=lambda item: item.device_id):
        lines = [f"### device_id {entry.device_id}"]
        lines += [f"- {rating.name}: {rating.value:g} {rating.unit}" for rating in entry.ratings]
        if entry.notes:
            lines.append(entry.notes)
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _render_links(prompt: SitePrompt, document_titles: dict[str, str]) -> str | None:
    """The 'Related:' line under a prompt: what it is about, so the AI calls the right tool."""
    links = prompt.links
    related = [f"point {point.point_name} (device_id {point.device_id})" for point in links.points]
    related += [f"site function {name}" for name in links.functions]
    related += [
        f"document '{document_titles[document_id]}'"
        for document_id in links.documents
        if document_id in document_titles  # a document not published yet isn't shown
    ]
    related += [f"ratings of device_id {device_id}" for device_id in links.devices]
    return f"Related: {'; '.join(related)}" if related else None


def _render_prompts(
    prompts: list[SitePrompt], document_titles: dict[str, str] | None = None
) -> str | None:
    if not prompts:
        return None
    parts = ["## About this site (from the site admin)"]
    for prompt in sorted(prompts, key=lambda item: (item.position, item.prompt_id)):
        section = f"### {prompt.name}\n{prompt.text}"
        related = _render_links(prompt, document_titles or {})
        if related:
            section += f"\n{related}"
        parts.append(section)
    return "\n\n".join(parts)


def render_knowledge(
    documents: list[KnowledgeDocument],
    facts: list[DeviceFacts] | None = None,
    prompts: list[SitePrompt] | None = None,
) -> str:
    """Deterministic text (stable order, no timestamps of the request) so the prompt cache hits.
    The admin's site prompts come first: the general picture before the details."""
    sections: list[str] = []
    titles = {document.document_id: document.title for document in documents}
    prompts_text = _render_prompts(prompts or [], titles)
    if prompts_text:
        sections.append(prompts_text)
    facts_text = _render_facts(facts or [])
    if facts_text:
        sections.append(facts_text)
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
        text = render_knowledge(
            await self._store.list_documents(site_id),
            await self._store.list_device_facts(site_id),
            await self._store.list_site_prompts(site_id),
        )
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
