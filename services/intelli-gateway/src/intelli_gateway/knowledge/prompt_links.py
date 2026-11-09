"""Which site prompts an item belongs to: the reverse of a prompt's links. The AI tools add these
to their results ("related_prompts") so the AI goes back to the admin's prompt for the context."""

from collections.abc import Iterable, Sequence

from intelli_gateway.schemas.knowledge import SiteScript


def prompt_label(script: SiteScript, number: int) -> str:
    return f"Prompt {number}: {script.name}"


def _numbered(scripts: Sequence[SiteScript]) -> list[tuple[int, SiteScript]]:
    ordered = sorted(scripts, key=lambda script: (script.position, script.script_id))
    return list(enumerate(ordered, start=1))


def related_prompts(
    scripts: Sequence[SiteScript],
    *,
    device_id: int | None = None,
    point_names: Iterable[str] = (),
    function: str | None = None,
    document_id: str | None = None,
) -> list[str]:
    """The prompts (as 'Prompt N: name', in the admin's order) linked to this point (device_id
    plus any of its names: qualified or local), device ratings (device_id alone), site function
    or document."""
    names = set(point_names)
    related: list[str] = []
    for number, script in _numbered(scripts):
        links = script.links
        linked = (
            (function is not None and function in links.functions)
            or (document_id is not None and document_id in links.documents)
            or (
                device_id is not None
                and names
                and any(
                    point.device_id == device_id and point.point_name in names
                    for point in links.points
                )
            )
            or (device_id is not None and not names and device_id in links.devices)
        )
        if linked:
            related.append(prompt_label(script, number))
    return related


def prompts_about_device(scripts: Sequence[SiteScript], device_id: int) -> list[str]:
    """The prompts linked to this device's ratings or to any of its points."""
    return [
        prompt_label(script, number)
        for number, script in _numbered(scripts)
        if device_id in script.links.devices
        or any(point.device_id == device_id for point in script.links.points)
    ]


def local_name(qualified_name: str, device_name: str | None) -> str:
    """A point's name on its device (the qualified name without `DEVICE.`)."""
    return qualified_name.removeprefix(f"{device_name}.") if device_name else qualified_name
