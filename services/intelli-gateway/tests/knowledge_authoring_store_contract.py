"""The KnowledgeAuthoringStore contract, shared by the in-memory fake (unit tests) and Postgres
(tests/integration): every implementation must pass these checks unchanged."""

from datetime import UTC, datetime, timedelta

import pytest

from intelli_gateway.interfaces.knowledge_authoring_store import KnowledgeAuthoringStore
from intelli_gateway.schemas.knowledge import (
    DeviceFacts,
    DeviceRating,
    GuideSeverity,
    KnowledgeDocument,
    KnowledgeDraft,
    KnowledgeKind,
    KnowledgeVersion,
    PointGuide,
    SiteKnowledge,
    StateGuide,
    StateKind,
)
from intelli_gateway.utils.exceptions import ConflictError

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)


def content(meaning: str = "Fault code of the meter") -> SiteKnowledge:
    return SiteKnowledge(
        point_guides=(
            PointGuide(
                site_id=1,
                device_id=1,
                point_name="Fault",
                meaning=meaning,
                states=(
                    StateGuide(
                        kind=StateKind.FAULT_CODE,
                        code=3,
                        label="CT_OPEN",
                        severity=GuideSeverity.FAULT,
                        message="A current transformer is open",
                        checks=("Check the CT wiring",),
                    ),
                ),
                author="ana@example.com",
                updated_at=NOW,
            ),
        ),
        documents=(
            KnowledgeDocument(
                document_id="doc-1",
                site_id=1,
                kind=KnowledgeKind.PROCEDURE,
                title="Meter reset",
                body="1. Open the panel\n2. Press reset",
                device_id=1,
                updated_at=NOW,
            ),
        ),
        device_facts=(
            DeviceFacts(
                site_id=1,
                device_id=1,
                ratings=(DeviceRating(name="CT ratio", value=400, unit="A/5A"),),
                updated_at=NOW,
            ),
        ),
    )


def draft(
    revision: int, site_id: int = 1, meaning: str = "Fault code of the meter"
) -> KnowledgeDraft:
    return KnowledgeDraft(
        site_id=site_id,
        revision=revision,
        content=content(meaning),
        updated_at=NOW + timedelta(minutes=revision),
        updated_by="ana@example.com",
    )


def version(number: int, site_id: int = 1, restored_from: int | None = None) -> KnowledgeVersion:
    return KnowledgeVersion(
        site_id=site_id,
        version=number,
        content=content(f"meaning v{number}"),
        published_at=NOW + timedelta(hours=number),
        published_by="ana@example.com",
        change_ids=("point:1:Fault",),
        restored_from=restored_from,
    )


async def nothing_at_first(store: KnowledgeAuthoringStore) -> None:
    assert await store.get_draft(1) is None
    assert await store.get_version(1) is None
    assert await store.list_versions(1) == []


async def drafts_read_back_and_need_the_next_revision(store: KnowledgeAuthoringStore) -> None:
    await store.save_draft(draft(1))
    assert await store.get_draft(1) == draft(1)  # nested guides, documents, facts round-trip
    with pytest.raises(ConflictError):
        await store.save_draft(draft(1, meaning="someone else's edit"))
    with pytest.raises(ConflictError):
        await store.save_draft(draft(3))
    await store.save_draft(draft(2, meaning="edited"))
    stored = await store.get_draft(1)
    assert stored is not None and stored.content.point_guides[0].meaning == "edited"
    assert await store.get_draft(2) is None
    await store.delete_draft(1)
    assert await store.get_draft(1) is None


async def a_first_draft_starts_at_revision_one(store: KnowledgeAuthoringStore) -> None:
    with pytest.raises(ConflictError):
        await store.save_draft(draft(2))
    await store.save_draft(draft(1))


async def publishing_stores_the_version_and_ends_the_draft(
    store: KnowledgeAuthoringStore,
) -> None:
    await store.save_draft(draft(1))
    await store.save_draft(draft(2))
    with pytest.raises(ConflictError):  # reviewed at revision 1, edited since
        await store.publish(version(1), draft_revision=1)
    assert await store.get_version(1) is None
    await store.publish(version(1), draft_revision=2)
    assert await store.get_draft(1) is None
    assert await store.get_version(1) == version(1)
    assert await store.get_version(1, 1) == version(1)


async def versions_are_listed_newest_first_and_taken_once(store: KnowledgeAuthoringStore) -> None:
    await store.publish(version(1), draft_revision=None)
    await store.publish(version(2, restored_from=1), draft_revision=None)
    await store.publish(version(1, site_id=2), draft_revision=None)
    with pytest.raises(ConflictError):
        await store.publish(version(2), draft_revision=None)
    assert [v.version for v in await store.list_versions(1)] == [2, 1]
    latest = await store.get_version(1)
    assert latest is not None and latest.version == 2 and latest.restored_from == 1
    assert await store.get_version(1, 7) is None


CHECKS = [
    nothing_at_first,
    drafts_read_back_and_need_the_next_revision,
    a_first_draft_starts_at_revision_one,
    publishing_stores_the_version_and_ends_the_draft,
    versions_are_listed_newest_first_and_taken_once,
]
