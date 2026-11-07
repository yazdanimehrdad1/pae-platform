"""Admin CLI for site profiles: the code-level way to onboard a site and approve backend-ot changes
(the web UI comes later; the admin API is under /api/v1/site-profiles). Runs where the service
runs, against its DATABASE_URL and backend-ot, and applies pending migrations first:

    python -m intelli_gateway.manage_site_profiles status
    python -m intelli_gateway.manage_site_profiles sync --site 1001        # read backend-ot now
    python -m intelli_gateway.manage_site_profiles changes --site 1001     # what waits
    python -m intelli_gateway.manage_site_profiles approve --site 1001 --by ana@example.com
    python -m intelli_gateway.manage_site_profiles approve --site 1001 --by ana@example.com \\
        --change device:12 --change point:12:active_power

`approve` without --change approves every pending change, from the last sync (run `changes`
first to see them). In the dev stack:
`docker compose -p pae-dev exec intelli-gateway python -m intelli_gateway.manage_site_profiles ...`
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime

from intelli_gateway.config import load_settings
from intelli_gateway.schemas.site_profile import PendingChanges
from intelli_gateway.services.backend_ot.client import BackendOtClient
from intelli_gateway.services.backend_ot.site_data import BackendOtSiteDataConnector
from intelli_gateway.services.postgres.database import (
    create_database_engine,
    migrate,
    wait_for_database,
)
from intelli_gateway.services.postgres.site_profile_store import PostgresSiteProfileStore
from intelli_gateway.site_profile.service import SiteProfileService
from intelli_gateway.utils.exceptions import GatewayError


def _changes_text(pending: PendingChanges) -> str:
    header = (
        f"site {pending.site_id}: approved version {pending.approved_version or 'none'}, "
        f"backend-ot read at {pending.fetched_at.isoformat()}"
    )
    if not pending.changes:
        return f"{header}\nno pending changes"
    lines = [f"  {change.change_id:<40} {change.summary}" for change in pending.changes]
    return "\n".join([header, f"{len(lines)} pending changes:", *lines])


async def _run(args: argparse.Namespace) -> str:
    settings = load_settings()
    if settings.database_url is None:
        raise SystemExit(
            "DATABASE_URL is not set: site profiles are stored in this service's Postgres"
        )
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
        if args.command == "status":
            statuses = await profiles.statuses()
            if not statuses:
                return "no site synced or onboarded yet (run sync)"
            return "\n".join(
                f"site {s.site_id:<6} {s.name:<30} approved v{s.approved_version or '-'}  "
                f"pending {s.pending_changes}"
                for s in statuses
            )
        if args.command == "sync":
            return _changes_text(await profiles.sync_site(args.site))
        if args.command == "changes":
            return _changes_text(await profiles.pending_changes(args.site))
        if args.command == "approve":
            version = await profiles.approve(args.site, args.by, change_ids=args.change or None)
            return (
                f"site {args.site}: approved version {version.version} "
                f"({len(version.change_ids)} changes, {len(version.catalog.devices)} devices, "
                f"{len(version.catalog.points)} points)"
            )
        raise SystemExit(f"unknown command {args.command}")
    finally:
        await engine.dispose()
        await source.aclose()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Onboard sites and approve backend-ot changes.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="every synced or onboarded site")
    for name, help_text in (
        ("sync", "read the site from backend-ot now"),
        ("changes", "list the pending changes"),
    ):
        commands.add_parser(name, help=help_text).add_argument("--site", type=int, required=True)
    approve = commands.add_parser("approve", help="approve pending changes")
    approve.add_argument("--site", type=int, required=True)
    approve.add_argument("--by", required=True, help="who approves (recorded with the version)")
    approve.add_argument(
        "--change", action="append", help="a change id to approve (repeat); default: all"
    )
    args = parser.parse_args(argv)
    try:
        print(asyncio.run(_run(args)))  # noqa: T201 (CLI output)
    except GatewayError as error:
        raise SystemExit(f"error: {error}") from error


if __name__ == "__main__":
    sys.exit(main())
