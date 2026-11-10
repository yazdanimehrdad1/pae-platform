"""SiteKnowledgeService: authoring a site's engineer knowledge (admins only) and the published
version the AI reads (docs/KNOWLEDGE_PLAN.md, step 2).

- Every edit goes to the site's draft: the whole knowledge as it will be once published. The
  first edit starts the draft from the published knowledge. An edit can name the draft revision
  it was made against (`draft_revision`, 0 = no draft yet); a ConflictError when it moved since.
- A publish takes the whole draft as the next version (option A: the site at once). Single
  drafts can be put back as published first (revert). Restore makes a new version with an
  earlier version's content. Older versions can be deleted, never the one the AI uses.
- Every item is checked against the approved site profile (approved devices and points only)
  and for secrets before it reaches the draft.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from intelli_gateway.interfaces.knowledge_authoring_store import KnowledgeAuthoringStore
from intelli_gateway.knowledge.authoring import (
    check_prompt_documents,
    coverage,
    diff_knowledge,
    document_key,
    facts_key,
    find_document,
    find_prompt,
    guide_key,
    next_prompt_position,
    prompt_key,
    revert_items,
    validate_item,
    with_item,
    without_document_links,
    without_item,
)
from intelli_gateway.schemas.knowledge import (
    DeviceFacts,
    DeviceRating,
    KnowledgeChange,
    KnowledgeCoverage,
    KnowledgeDocument,
    KnowledgeDraft,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeVersion,
    LimitGuide,
    NormalRange,
    PointGuide,
    SiteKnowledge,
    SitePrompt,
    SitePromptLinks,
    StateGuide,
)
from intelli_gateway.schemas.site_profile import SiteCatalog
from intelli_gateway.site_profile.service import SiteProfileService
from intelli_gateway.utils.exceptions import ConflictError, InvalidRequestError, NotFoundError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GuideContent:
    meaning: str
    unit_note: str | None = None
    normal_range: NormalRange | None = None
    related_points: tuple[str, ...] = ()
    limits: tuple[LimitGuide, ...] = ()
    states: tuple[StateGuide, ...] = ()


@dataclass(frozen=True)
class DocumentContent:
    kind: KnowledgeKind
    title: str
    body: str
    device_id: int | None = None
    point_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class KnowledgeState:
    """The site's knowledge as an admin sees it: published version, and the draft if any."""

    site_id: int
    published: KnowledgeVersion | None
    draft: KnowledgeDraft | None
    changes: tuple[KnowledgeChange, ...]

    @property
    def working(self) -> SiteKnowledge:
        """What the next publish would contain."""
        if self.draft is not None:
            return self.draft.content
        return self.published.content if self.published else SiteKnowledge()

    @property
    def draft_revision(self) -> int:
        return self.draft.revision if self.draft else 0


@dataclass(frozen=True)
class _Cached:
    version: KnowledgeVersion | None
    loaded_at: datetime


class SiteKnowledgeService:
    def __init__(
        self,
        store: KnowledgeAuthoringStore,
        profiles: SiteProfileService,
        clock: Callable[[], datetime],
        cache_ttl_s: float = 30,
    ) -> None:
        self._store = store
        self._profiles = profiles
        self._clock = clock
        self._cache_ttl = timedelta(seconds=cache_ttl_s)
        self._published: dict[int, _Cached] = {}

    # --- reading ---

    async def published(self, site_id: int) -> KnowledgeVersion | None:
        """The version the AI uses (cached for a short TTL; this instance's publish drops it)."""
        now = self._clock()
        cached = self._published.get(site_id)
        if cached is not None and now - cached.loaded_at < self._cache_ttl:
            return cached.version
        version = await self._store.get_version(site_id)
        self._published[site_id] = _Cached(version=version, loaded_at=now)
        return version

    async def state(self, site_id: int) -> KnowledgeState:
        await self._catalog(site_id)
        published = await self._store.get_version(site_id)
        draft = await self._store.get_draft(site_id)
        changes = (
            diff_knowledge(published.content if published else SiteKnowledge(), draft.content)
            if draft
            else []
        )
        return KnowledgeState(
            site_id=site_id, published=published, draft=draft, changes=tuple(changes)
        )

    async def version(self, site_id: int, version: int) -> KnowledgeVersion:
        found = await self._store.get_version(site_id, version)
        if found is None:
            raise NotFoundError(f"no knowledge version {version}")
        return found

    async def versions(self, site_id: int) -> list[KnowledgeVersion]:
        return await self._store.list_versions(site_id)

    async def coverage(self, site_id: int) -> KnowledgeCoverage:
        catalog = await self._catalog(site_id)
        return coverage(site_id, (await self.state(site_id)).working, catalog)

    # --- edits (each one saves the next draft revision) ---

    async def put_point_guide(
        self,
        site_id: int,
        device_id: int,
        point_name: str,
        content: GuideContent,
        author: str,
        draft_revision: int | None = None,
    ) -> KnowledgeState:
        guide = PointGuide(
            site_id=site_id,
            device_id=device_id,
            point_name=point_name,
            meaning=content.meaning,
            unit_note=content.unit_note,
            normal_range=content.normal_range,
            related_points=content.related_points,
            limits=content.limits,
            states=content.states,
            author=author,
            updated_at=self._clock(),
        )
        return await self._edit(
            site_id, author, draft_revision, lambda knowledge: with_item(knowledge, guide), guide
        )

    async def delete_point_guide(
        self,
        site_id: int,
        device_id: int,
        point_name: str,
        author: str,
        draft_revision: int | None = None,
    ) -> KnowledgeState:
        key = guide_key(device_id, point_name)
        return await self._edit(
            site_id, author, draft_revision, lambda knowledge: without_item(knowledge, key)
        )

    async def create_document(
        self, site_id: int, content: DocumentContent, author: str, draft_revision: int | None = None
    ) -> tuple[KnowledgeState, str]:
        document = self._document(site_id, content, author)
        state = await self._edit(
            site_id,
            author,
            draft_revision,
            lambda knowledge: with_item(knowledge, document),
            document,
        )
        return state, document.document_id

    async def update_document(
        self,
        site_id: int,
        document_id: str,
        content: DocumentContent,
        author: str,
        draft_revision: int | None = None,
    ) -> KnowledgeState:
        document = self._document(site_id, content, author, document_id)

        def change(knowledge: SiteKnowledge) -> SiteKnowledge:
            find_document(knowledge, document_id)  # NotFoundError for an unknown id
            return with_item(knowledge, document)

        return await self._edit(site_id, author, draft_revision, change, document)

    async def delete_document(
        self, site_id: int, document_id: str, author: str, draft_revision: int | None = None
    ) -> KnowledgeState:
        key = document_key(document_id)
        return await self._edit(
            site_id,
            author,
            draft_revision,
            lambda knowledge: without_document_links(without_item(knowledge, key), document_id),
        )

    async def create_site_prompt(
        self,
        site_id: int,
        name: str,
        text: str,
        author: str,
        draft_revision: int | None = None,
        links: SitePromptLinks | None = None,
    ) -> tuple[KnowledgeState, str]:
        """Add a site prompt after the others."""
        prompt = self._prompt(site_id, name, text, author, links=links)

        def change(knowledge: SiteKnowledge) -> SiteKnowledge:
            check_prompt_documents(prompt, knowledge)
            placed = prompt.model_copy(update={"position": next_prompt_position(knowledge)})
            return with_item(knowledge, placed)

        state = await self._edit(site_id, author, draft_revision, change, prompt)
        return state, prompt.prompt_id

    async def update_site_prompt(
        self,
        site_id: int,
        prompt_id: str,
        name: str,
        text: str,
        author: str,
        draft_revision: int | None = None,
        links: SitePromptLinks | None = None,
    ) -> KnowledgeState:
        """Change a site prompt's name, text and links; it keeps its place."""
        prompt = self._prompt(site_id, name, text, author, prompt_id, links)

        def change(knowledge: SiteKnowledge) -> SiteKnowledge:
            check_prompt_documents(prompt, knowledge)
            position = find_prompt(knowledge, prompt_id).position  # NotFoundError: unknown id
            return with_item(knowledge, prompt.model_copy(update={"position": position}))

        return await self._edit(site_id, author, draft_revision, change, prompt)

    async def delete_site_prompt(
        self, site_id: int, prompt_id: str, author: str, draft_revision: int | None = None
    ) -> KnowledgeState:
        key = prompt_key(prompt_id)
        return await self._edit(
            site_id, author, draft_revision, lambda knowledge: without_item(knowledge, key)
        )

    async def put_device_facts(
        self,
        site_id: int,
        device_id: int,
        ratings: Sequence[DeviceRating],
        notes: str | None,
        author: str,
        draft_revision: int | None = None,
    ) -> KnowledgeState:
        facts = DeviceFacts(
            site_id=site_id,
            device_id=device_id,
            ratings=tuple(ratings),
            notes=notes or None,
            author=author,
            updated_at=self._clock(),
        )
        return await self._edit(
            site_id, author, draft_revision, lambda knowledge: with_item(knowledge, facts), facts
        )

    async def delete_device_facts(
        self, site_id: int, device_id: int, author: str, draft_revision: int | None = None
    ) -> KnowledgeState:
        key = facts_key(device_id)
        return await self._edit(
            site_id, author, draft_revision, lambda knowledge: without_item(knowledge, key)
        )

    async def revert(
        self, site_id: int, item_keys: Sequence[str], author: str, draft_revision: int | None = None
    ) -> KnowledgeState:
        """Put these draft items back as published. A draft left with no change is dropped."""
        state = await self.state(site_id)
        if state.draft is None:
            raise InvalidRequestError("there is no draft")
        published = state.published.content if state.published else SiteKnowledge()
        return await self._edit(
            site_id,
            author,
            draft_revision,
            lambda knowledge: revert_items(knowledge, published, item_keys),
        )

    async def discard_draft(self, site_id: int) -> KnowledgeState:
        await self._store.delete_draft(site_id)
        return await self.state(site_id)

    async def import_content(
        self, site_id: int, content: SiteKnowledge, author: str
    ) -> KnowledgeState:
        """Replace the draft with this knowledge (an export, the code-level way in). Every item
        is checked as if edited one by one; ids and the site are taken from here."""
        catalog = await self._catalog(site_id)
        now = self._clock()
        items: list[KnowledgeItem] = [
            *(
                g.model_copy(update={"site_id": site_id, "author": author, "updated_at": now})
                for g in content.point_guides
            ),
            *(
                d.model_copy(update={"site_id": site_id, "author": author, "updated_at": now})
                for d in content.documents
            ),
            *(
                f.model_copy(update={"site_id": site_id, "author": author, "updated_at": now})
                for f in content.device_facts
            ),
            *(
                s.model_copy(update={"site_id": site_id, "author": author, "updated_at": now})
                for s in content.site_prompts
            ),
        ]
        for item in items:
            validate_item(item, catalog)
        imported = SiteKnowledge()
        for item in items:
            imported = with_item(imported, item)
        for prompt in imported.site_prompts:
            check_prompt_documents(prompt, imported)
        return await self._edit(site_id, author, None, lambda knowledge: imported)

    # --- publishing ---

    async def publish(
        self, site_id: int, author: str, draft_revision: int | None = None
    ) -> KnowledgeVersion:
        """The whole draft becomes the next version; the AI uses it from now on."""
        state = await self.state(site_id)
        if state.draft is None or not state.changes:
            raise InvalidRequestError("nothing to publish: the draft has no changes")
        if draft_revision is not None and draft_revision != state.draft.revision:
            raise ConflictError("the draft was changed since you reviewed it; review it again")
        version = KnowledgeVersion(
            site_id=site_id,
            version=(state.published.version + 1) if state.published else 1,
            content=state.draft.content,
            published_at=self._clock(),
            published_by=author,
            change_ids=tuple(change.item_key for change in state.changes),
        )
        await self._store.publish(version, state.draft.revision)
        self._published.pop(site_id, None)
        logger.info(
            "knowledge_published",
            extra={
                "fields": {
                    "site_id": site_id,
                    "version": version.version,
                    "changes": len(state.changes),
                    "published_by": author,
                }
            },
        )
        return version

    async def restore(self, site_id: int, version: int, author: str) -> KnowledgeVersion:
        """A new version with an earlier version's content (a rollback that keeps history)."""
        state = await self.state(site_id)
        if state.draft is not None:
            raise ConflictError("publish or discard the draft before restoring a version")
        old = await self.version(site_id, version)
        current = state.published
        if current is None or current.version == version:
            raise InvalidRequestError(f"version {version} is already what the AI uses")
        restored = KnowledgeVersion(
            site_id=site_id,
            version=current.version + 1,
            content=old.content,
            published_at=self._clock(),
            published_by=author,
            change_ids=tuple(
                change.item_key for change in diff_knowledge(current.content, old.content)
            ),
            restored_from=version,
        )
        await self._store.publish(restored, None)
        self._published.pop(site_id, None)
        return restored

    async def delete_versions(
        self, site_id: int, versions: Sequence[int], author: str
    ) -> list[KnowledgeVersion]:
        """Delete older published versions (history only); never the one the AI uses, so what
        the AI knows doesn't change. Returns the versions left, newest first."""
        wanted = sorted(set(versions))
        if not wanted:
            raise InvalidRequestError("choose at least one version to delete")
        stored = {entry.version for entry in await self._store.list_versions(site_id)}
        missing = [number for number in wanted if number not in stored]
        if missing:
            raise NotFoundError(f"no knowledge version {', '.join(map(str, missing))}")
        live = max(stored)
        if live in wanted:
            raise InvalidRequestError(
                f"version {live} is what the AI uses and can't be deleted; "
                "restore an older version first to replace it"
            )
        deleted = await self._store.delete_versions(site_id, wanted)
        logger.info(
            "knowledge_versions_deleted",
            extra={"fields": {"site_id": site_id, "versions": deleted, "deleted_by": author}},
        )
        return await self._store.list_versions(site_id)

    # --- helpers ---

    async def _catalog(self, site_id: int) -> SiteCatalog:
        view = await self._profiles.approved_view(site_id)
        if view is None:
            raise NotFoundError("site not onboarded: approve its profile first")
        return view.catalog

    def _document(
        self, site_id: int, content: DocumentContent, author: str, document_id: str | None = None
    ) -> KnowledgeDocument:
        values = {
            "site_id": site_id,
            "kind": content.kind,
            "title": content.title.strip(),
            "body": content.body,
            "device_id": content.device_id,
            "point_names": content.point_names,
            "author": author,
            "updated_at": self._clock(),
        }
        if document_id is not None:
            values["document_id"] = document_id
        return KnowledgeDocument.model_validate(values)

    def _prompt(
        self,
        site_id: int,
        name: str,
        text: str,
        author: str,
        prompt_id: str | None = None,
        links: SitePromptLinks | None = None,
    ) -> SitePrompt:
        values: dict[str, object] = {
            "site_id": site_id,
            "name": name.strip(),
            "text": text,
            "position": 1,  # placed by the edit
            "links": links or SitePromptLinks(),
            "author": author,
            "updated_at": self._clock(),
        }
        if prompt_id is not None:
            values["prompt_id"] = prompt_id
        return SitePrompt.model_validate(values)

    async def _edit(
        self,
        site_id: int,
        author: str,
        draft_revision: int | None,
        change: Callable[[SiteKnowledge], SiteKnowledge],
        item: KnowledgeItem | None = None,
    ) -> KnowledgeState:
        catalog = await self._catalog(site_id)
        if item is not None:
            validate_item(item, catalog)
        state = await self.state(site_id)
        if draft_revision is not None and draft_revision != state.draft_revision:
            raise ConflictError("the draft was changed since you loaded it; reload it")
        content = change(state.working)
        published = state.published.content if state.published else SiteKnowledge()
        if state.draft is not None and not diff_knowledge(published, content):
            await self._store.delete_draft(site_id)  # back to the published knowledge
            return await self.state(site_id)
        await self._store.save_draft(
            KnowledgeDraft(
                site_id=site_id,
                revision=state.draft_revision + 1,
                content=content,
                updated_at=self._clock(),
                updated_by=author,
            )
        )
        return await self.state(site_id)
