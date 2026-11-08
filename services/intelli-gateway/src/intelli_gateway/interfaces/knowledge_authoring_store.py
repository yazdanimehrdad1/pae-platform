"""Where a site's engineer knowledge is kept for authoring: one draft per site (the unpublished
edits) and every published version. Implementations: Postgres
(services/postgres/knowledge_authoring_store.py) and in memory in tests
(tests/doubles/knowledge_authoring_store.py), both checked by
tests/knowledge_authoring_store_contract.py. The AI reads only published versions
(knowledge/published_store.py)."""

from typing import Protocol

from intelli_gateway.schemas.knowledge import KnowledgeDraft, KnowledgeVersion


class KnowledgeAuthoringStore(Protocol):
    async def get_draft(self, site_id: int) -> KnowledgeDraft | None: ...

    async def save_draft(self, draft: KnowledgeDraft) -> None:
        """Store the draft. Its `revision` must be exactly one more than the stored draft's (or 1
        with no stored draft); otherwise a ConflictError: someone else saved in between."""
        ...

    async def delete_draft(self, site_id: int) -> None: ...

    async def get_version(
        self, site_id: int, version: int | None = None
    ) -> KnowledgeVersion | None:
        """That version, or the latest one when version is None; None when there is none."""
        ...

    async def list_versions(self, site_id: int) -> list[KnowledgeVersion]:
        """Every published version of the site, newest first."""
        ...

    async def publish(self, version: KnowledgeVersion, draft_revision: int | None) -> None:
        """Store the new version and, in the same transaction, delete the draft it came from.
        ConflictError when the version number is taken, or when draft_revision is given and the
        stored draft is no longer at that revision (it was edited since it was reviewed)."""
        ...
