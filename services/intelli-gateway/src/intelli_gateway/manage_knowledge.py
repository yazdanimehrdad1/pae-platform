"""Admin CLI for a site's engineer knowledge: the code-level way in, next to the web UI. Runs where
the service runs, against its DATABASE_URL and backend-ot (the site profile), and applies pending
migrations first:

    python -m intelli_gateway.manage_knowledge status --site 1002
    python -m intelli_gateway.manage_knowledge export --site 1002 --file /tmp/site-1002.json
    python -m intelli_gateway.manage_knowledge import --site 1002 --file /tmp/site-1002.json \\
        --by ana@example.com
    python -m intelli_gateway.manage_knowledge publish --site 1002 --by ana@example.com
    python -m intelli_gateway.manage_knowledge seed powerflow_2bess_1pv --by ana@example.com

`export` writes the published knowledge (or `--draft`) as JSON. `import` replaces the site's draft
with a file's content, checked like edits in the UI (approved devices and points only, no
secrets); then review it and `publish`. `seed` does both with a code-level seed
(`knowledge/seeds/`, simulated powerflow sites only), on the site it names unless `--site` is
given; it replaces the site's knowledge (earlier versions stay restorable). Keep export files
out of the repository: they hold real plant knowledge. In the dev stack:
`docker compose -p pae-dev exec intelli-gateway python -m intelli_gateway.manage_knowledge ...`
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from intelli_gateway.config import load_settings
from intelli_gateway.knowledge.seeds import SEEDS
from intelli_gateway.knowledge.service import KnowledgeState, SiteKnowledgeService
from intelli_gateway.schemas.knowledge import SiteKnowledge
from intelli_gateway.services.backend_ot.client import BackendOtClient
from intelli_gateway.services.backend_ot.site_data import BackendOtSiteDataConnector
from intelli_gateway.services.postgres.database import (
    create_database_engine,
    migrate,
    wait_for_database,
)
from intelli_gateway.services.postgres.knowledge_authoring_store import (
    PostgresKnowledgeAuthoringStore,
)
from intelli_gateway.services.postgres.site_profile_store import PostgresSiteProfileStore
from intelli_gateway.site_profile.service import SiteProfileService
from intelli_gateway.utils.exceptions import GatewayError


def _status_text(state: KnowledgeState) -> str:
    published = (
        f"published v{state.published.version} ({state.published.published_at.isoformat()}, "
        f"{state.published.published_by})"
        if state.published
        else "nothing published"
    )
    content = state.working
    lines = [
        f"site {state.site_id}: {published}",
        f"draft: revision {state.draft_revision}, {len(state.changes)} change(s) to publish"
        if state.draft
        else "no draft",
        f"{len(content.point_guides)} point guides, {len(content.documents)} documents, "
        f"{len(content.device_facts)} device facts",
    ]
    lines += [f"  {change.summary}" for change in state.changes]
    return "\n".join(lines)


async def _seed(
    args: argparse.Namespace, profiles: SiteProfileService, knowledge: SiteKnowledgeService
) -> str:
    seed = SEEDS[args.name]
    site_id: int | None = args.site
    if site_id is None:
        matches = [s.site_id for s in await profiles.approved_sites() if s.name == seed.site_name]
        if len(matches) != 1:
            raise SystemExit(
                f"{len(matches)} approved sites are named {seed.site_name!r}: pass --site"
            )
        site_id = matches[0]
    view = await profiles.approved_view(site_id)
    if view is None:
        raise SystemExit(f"site {site_id} is not onboarded: approve its profile first")
    state = await knowledge.import_content(site_id, seed.build(view.catalog), args.by)
    if not state.changes:
        # The import saved the unchanged knowledge as a draft: drop it, nothing to review.
        state = await knowledge.discard_draft(site_id)
        return _status_text(state) + "\nalready seeded: nothing changed"
    if args.no_publish:
        return _status_text(state) + "\nreview it, then publish"
    version = await knowledge.publish(site_id, args.by)
    return (
        _status_text(await knowledge.state(site_id))
        + f"\npublished v{version.version} ({len(version.change_ids)} changes)"
    )


async def _run(args: argparse.Namespace) -> str:
    settings = load_settings()
    if settings.database_url is None:
        raise SystemExit("DATABASE_URL is not set: knowledge is stored in this service's Postgres")
    clock = lambda: datetime.now(UTC)  # noqa: E731
    source = BackendOtSiteDataConnector(
        BackendOtClient(
            settings.backend_ot_url, settings.backend_ot_timeout_s, settings.backend_ot_retries
        ),
        stale_after_s=settings.data_stale_after_s,
        clock=clock,
    )
    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        await wait_for_database(engine)
        await migrate(engine)
        profiles = SiteProfileService(PostgresSiteProfileStore(engine), source, clock)
        knowledge = SiteKnowledgeService(PostgresKnowledgeAuthoringStore(engine), profiles, clock)
        if args.command == "status":
            return _status_text(await knowledge.state(args.site))
        if args.command == "export":
            state = await knowledge.state(args.site)
            content = (
                state.working
                if args.draft
                else (state.published.content if state.published else SiteKnowledge())
            )
            Path(args.file).write_text(content.model_dump_json(indent=2), encoding="utf-8")
            return f"wrote {args.file}"
        if args.command == "import":
            content = SiteKnowledge.model_validate_json(Path(args.file).read_text(encoding="utf-8"))
            state = await knowledge.import_content(args.site, content, args.by)
            return _status_text(state) + "\nreview it, then publish"
        if args.command == "seed":
            return await _seed(args, profiles, knowledge)
        if args.command == "publish":
            version = await knowledge.publish(args.site, args.by)
            changes = len(version.change_ids)
            return f"site {args.site}: published v{version.version} ({changes} changes)"
        raise SystemExit(f"unknown command {args.command}")
    finally:
        await engine.dispose()
        await source.aclose()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Manage a site's engineer knowledge.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="published version and draft").add_argument(
        "--site", type=int, required=True
    )
    export = commands.add_parser("export", help="write the knowledge to a JSON file")
    export.add_argument("--site", type=int, required=True)
    export.add_argument("--file", required=True)
    export.add_argument("--draft", action="store_true", help="the draft, not the published one")
    imported = commands.add_parser("import", help="replace the draft with a JSON file")
    imported.add_argument("--site", type=int, required=True)
    imported.add_argument("--file", required=True)
    imported.add_argument("--by", required=True, help="who imports (recorded as the author)")
    publish = commands.add_parser("publish", help="publish the whole draft")
    publish.add_argument("--site", type=int, required=True)
    publish.add_argument("--by", required=True)
    seed = commands.add_parser("seed", help="replace the knowledge with a code-level seed, publish")
    seed.add_argument("name", choices=sorted(SEEDS))
    seed.add_argument("--site", type=int, help="default: the approved site the seed names")
    seed.add_argument("--by", required=True, help="who seeds (recorded as the author)")
    seed.add_argument("--no-publish", action="store_true", help="leave it as a draft to review")
    args = parser.parse_args(argv)
    try:
        print(asyncio.run(_run(args)))  # noqa: T201 (CLI output)
    except GatewayError as error:
        raise SystemExit(f"error: {error}") from error


if __name__ == "__main__":
    sys.exit(main())
