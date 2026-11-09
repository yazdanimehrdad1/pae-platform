"""Editing a site's knowledge: item keys, the draft-vs-published diff, edits, validation against
the approved site profile, and coverage. Pure functions: no I/O."""

import re
from collections.abc import Collection, Iterable
from typing import Any, Literal

from intelli_gateway.schemas.knowledge import (
    DeviceFacts,
    KnowledgeChange,
    KnowledgeCoverage,
    KnowledgeDocument,
    KnowledgeItem,
    KnowledgeItemKind,
    MissingGuide,
    PointGuide,
    SiteKnowledge,
    SiteScript,
)
from intelli_gateway.schemas.site_data import PointClass
from intelli_gateway.schemas.site_profile import SiteCatalog
from intelli_gateway.site_profile.diff import local_point_name
from intelli_gateway.utils.exceptions import InvalidRequestError, NotFoundError

# --- item keys ------------------------------------------------------------------------------


def guide_key(device_id: int, point_name: str) -> str:
    return f"point:{device_id}:{point_name}"


def document_key(document_id: str) -> str:
    return f"document:{document_id}"


def facts_key(device_id: int) -> str:
    return f"device:{device_id}"


def script_key(script_id: str) -> str:
    return f"script:{script_id}"


def _key(item: KnowledgeItem) -> str:
    if isinstance(item, PointGuide):
        return guide_key(item.device_id, item.point_name)
    if isinstance(item, KnowledgeDocument):
        return document_key(item.document_id)
    if isinstance(item, SiteScript):
        return script_key(item.script_id)
    return facts_key(item.device_id)


def _items(content: SiteKnowledge) -> dict[str, KnowledgeItem]:
    every: list[KnowledgeItem] = [
        *content.point_guides,
        *content.documents,
        *content.device_facts,
        *content.site_scripts,
    ]
    return {_key(item): item for item in every}


# Who and when don't make an edit: only what the AI would read.
_BOOKKEEPING = {"author", "updated_at"}


def _same(old: Any, new: Any) -> bool:
    return old.model_dump(exclude=_BOOKKEEPING) == new.model_dump(exclude=_BOOKKEEPING)


def _describe(item: KnowledgeItem) -> tuple[KnowledgeItemKind, str]:
    if isinstance(item, PointGuide):
        return KnowledgeItemKind.POINT_GUIDE, f"guide for device {item.device_id} {item.point_name}"
    if isinstance(item, KnowledgeDocument):
        return KnowledgeItemKind.DOCUMENT, f"{item.kind.value.replace('_', ' ')} '{item.title}'"
    if isinstance(item, SiteScript):
        return KnowledgeItemKind.SITE_SCRIPT, f"site prompt '{item.name}'"
    return KnowledgeItemKind.DEVICE_FACTS, f"ratings and notes of device {item.device_id}"


def diff_knowledge(published: SiteKnowledge, draft: SiteKnowledge) -> list[KnowledgeChange]:
    """The draft items that differ from the published ones, by item key."""
    old, new = _items(published), _items(draft)
    changes: list[KnowledgeChange] = []
    for key in sorted(old.keys() | new.keys()):
        before, after = old.get(key), new.get(key)
        kind: Literal["added", "removed", "changed"]
        if before is None and after is not None:
            kind, item = "added", after
        elif after is None and before is not None:
            kind, item = "removed", before
        elif before is not None and after is not None and not _same(before, after):
            kind, item = "changed", after
        else:
            continue
        item_kind, description = _describe(item)
        changes.append(
            KnowledgeChange(
                item_key=key, item_kind=item_kind, kind=kind, summary=f"{kind}: {description}"
            )
        )
    return changes


def revert_items(
    draft: SiteKnowledge, published: SiteKnowledge, item_keys: Collection[str]
) -> SiteKnowledge:
    """The draft with these items put back as published (a draft-only item is dropped)."""
    pending = {change.item_key for change in diff_knowledge(published, draft)}
    unknown = sorted(set(item_keys) - pending)
    if unknown:
        raise InvalidRequestError(f"not changed in the draft: {', '.join(unknown)}")
    items, old = _items(draft), _items(published)
    for key in item_keys:
        if key in old:
            items[key] = old[key]
        else:
            items.pop(key, None)
    return _content(items.values())


def _content(items: Iterable[KnowledgeItem]) -> SiteKnowledge:
    guides: list[PointGuide] = []
    documents: list[KnowledgeDocument] = []
    facts: list[DeviceFacts] = []
    scripts: list[SiteScript] = []
    for item in items:
        if isinstance(item, PointGuide):
            guides.append(item)
        elif isinstance(item, KnowledgeDocument):
            documents.append(item)
        elif isinstance(item, SiteScript):
            scripts.append(item)
        else:
            facts.append(item)
    return SiteKnowledge(
        point_guides=tuple(sorted(guides, key=lambda g: (g.device_id, g.point_name))),
        documents=tuple(sorted(documents, key=lambda d: (d.kind.value, d.title, d.document_id))),
        device_facts=tuple(sorted(facts, key=lambda f: f.device_id)),
        site_scripts=tuple(sorted(scripts, key=lambda s: (s.position, s.script_id))),
    )


# --- edits ----------------------------------------------------------------------------------


def with_item(content: SiteKnowledge, item: KnowledgeItem) -> SiteKnowledge:
    items = _items(content)
    items[_key(item)] = item
    return _content(items.values())


def without_item(content: SiteKnowledge, item_key: str) -> SiteKnowledge:
    items = _items(content)
    if item_key not in items:
        raise NotFoundError(f"no {item_key} in the knowledge")
    del items[item_key]
    return _content(items.values())


def find_document(content: SiteKnowledge, document_id: str) -> KnowledgeDocument:
    for document in content.documents:
        if document.document_id == document_id:
            return document
    raise NotFoundError(f"no document {document_id}")


def find_script(content: SiteKnowledge, script_id: str) -> SiteScript:
    for script in content.site_scripts:
        if script.script_id == script_id:
            return script
    raise NotFoundError(f"no site script {script_id}")


def next_script_position(content: SiteKnowledge) -> int:
    """A new site script goes after the others."""
    return max((script.position for script in content.site_scripts), default=0) + 1


def without_document_links(content: SiteKnowledge, document_id: str) -> SiteKnowledge:
    """The knowledge with this document dropped from every site prompt's links."""
    scripts = tuple(
        script.model_copy(
            update={
                "links": script.links.model_copy(
                    update={
                        "documents": tuple(d for d in script.links.documents if d != document_id)
                    }
                )
            }
        )
        if document_id in script.links.documents
        else script
        for script in content.site_scripts
    )
    return content.model_copy(update={"site_scripts": scripts})


def check_script_documents(script: SiteScript, content: SiteKnowledge) -> None:
    """InvalidRequestError when the prompt links a document the knowledge doesn't have."""
    document_ids = {document.document_id for document in content.documents}
    for document_id in script.links.documents:
        if document_id not in document_ids:
            raise InvalidRequestError(f"no document {document_id} to link")


def unresolved_links(script: SiteScript, catalog: SiteCatalog) -> list[str]:
    """The prompt's links to points, functions or devices the approved profile no longer has."""
    approved = _approved_points(catalog)
    function_names = {function.name for function in catalog.functions}
    device_ids = {device.device_id for device in catalog.devices}
    unresolved = [
        f"point {point.device_id} {point.point_name}"
        for point in script.links.points
        if (point.device_id, point.point_name) not in approved
    ]
    unresolved += [
        f"site function '{name}'" for name in script.links.functions if name not in function_names
    ]
    unresolved += [
        f"device {device_id}" for device_id in script.links.devices if device_id not in device_ids
    ]
    return unresolved


# --- validation -----------------------------------------------------------------------------

_SECRETS = (
    (
        re.compile(r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|token)\b\s*[:=]\s*\S+"),
        "a credential",
    ),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "a private key"),
    (
        re.compile(
            r"(?<![\d.])(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}(?![\d.])"
        ),
        "an IP address",
    ),
)


def find_secret(text: str) -> str | None:
    """What kind of secret or network detail the text holds, or None. Knowledge never stores
    credentials, keys or addresses: the AI could repeat them."""
    for pattern, what in _SECRETS:
        if pattern.search(text):
            return what
    return None


def _texts(item: KnowledgeItem) -> list[str]:
    def walk(value: Any) -> Iterable[str]:
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for nested in value.values():  # pyright: ignore[reportUnknownVariableType]
                yield from walk(nested)
        elif isinstance(value, list | tuple):
            for nested in value:  # pyright: ignore[reportUnknownVariableType]
                yield from walk(nested)

    return list(walk(item.model_dump(exclude=_BOOKKEEPING)))


def _approved_points(catalog: SiteCatalog) -> dict[tuple[int, str], Any]:
    return {(point.device_id, local_point_name(point)): point for point in catalog.points}


def validate_item(item: KnowledgeItem, catalog: SiteCatalog) -> None:
    """InvalidRequestError when the item doesn't fit the approved site profile or holds a secret."""
    device_ids = {device.device_id for device in catalog.devices}
    for text in _texts(item):
        secret = find_secret(text)
        if secret:
            raise InvalidRequestError(f"remove {secret}: knowledge never stores it")
    if isinstance(item, PointGuide):
        if (item.device_id, item.point_name) not in _approved_points(catalog):
            raise InvalidRequestError(
                f"device {item.device_id} has no approved point '{item.point_name}'"
            )
        seen: set[tuple[str, int]] = set()
        for state in item.states:
            key = (state.kind.value, state.code)
            if key in seen:
                raise InvalidRequestError(f"two entries for {state.kind.value} {state.code}")
            seen.add(key)
        if (
            item.normal_range
            and item.normal_range.min is not None
            and item.normal_range.max is not None
        ):
            if item.normal_range.min > item.normal_range.max:
                raise InvalidRequestError("the normal range's min is above its max")
    elif isinstance(item, SiteScript):
        unresolved = unresolved_links(item, catalog)
        if unresolved:
            raise InvalidRequestError(f"not in the approved profile: {', '.join(unresolved)}")
    elif isinstance(item, KnowledgeDocument):
        if item.device_id is not None and item.device_id not in device_ids:
            raise InvalidRequestError(f"device {item.device_id} is not in the approved profile")
    else:
        if item.device_id not in device_ids:
            raise InvalidRequestError(f"device {item.device_id} is not in the approved profile")
        names = [rating.name.strip().lower() for rating in item.ratings]
        if len(names) != len(set(names)):
            raise InvalidRequestError("each rating name once")


# --- coverage -------------------------------------------------------------------------------


def _discrete_reason(point: Any) -> Literal["alarm", "states", "bits"] | None:
    if point.point_class is PointClass.ALARM:
        return "alarm"
    if point.bit_labels:
        return "bits"
    if point.enum_labels:
        return "states"
    return None


def coverage(site_id: int, content: SiteKnowledge, catalog: SiteCatalog) -> KnowledgeCoverage:
    approved = _approved_points(catalog)
    device_ids = {device.device_id for device in catalog.devices}
    guided = {(guide.device_id, guide.point_name) for guide in content.point_guides}
    missing: list[MissingGuide] = []
    discrete = 0
    for (device_id, name), point in sorted(approved.items()):
        reason = _discrete_reason(point)
        if reason is None:
            continue
        discrete += 1
        if (device_id, name) not in guided:
            missing.append(
                MissingGuide(
                    device_id=device_id,
                    point_name=name,
                    qualified_name=point.name,
                    point_class=point.point_class.value if point.point_class else None,
                    reason=reason,
                )
            )
    orphaned = [
        guide_key(guide.device_id, guide.point_name)
        for guide in content.point_guides
        if (guide.device_id, guide.point_name) not in approved
    ]
    orphaned += [
        document_key(document.document_id)
        for document in content.documents
        if document.device_id is not None and document.device_id not in device_ids
    ]
    orphaned += [
        facts_key(facts.device_id)
        for facts in content.device_facts
        if facts.device_id not in device_ids
    ]
    orphaned += [
        script_key(script.script_id)
        for script in content.site_scripts
        if unresolved_links(script, catalog)
    ]
    by_kind: dict[str, int] = {}
    for document in content.documents:
        by_kind[document.kind.value] = by_kind.get(document.kind.value, 0) + 1
    return KnowledgeCoverage(
        site_id=site_id,
        points=len(approved),
        discrete_points=discrete,
        discrete_with_guide=discrete - len(missing),
        missing_guides=tuple(missing),
        guides=len(content.point_guides),
        documents_by_kind=by_kind,
        devices=len(device_ids),
        devices_with_facts=sum(
            1 for facts in content.device_facts if facts.device_id in device_ids
        ),
        orphaned=tuple(orphaned),
    )
