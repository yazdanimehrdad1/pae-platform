"""Admin CLI for PlusDAS user accounts (there is no self-signup). Runs where the service runs,
against its DATABASE_URL, and applies pending migrations first:

    python -m intelli_gateway.manage_users create --email ana@example.com --role admin
    python -m intelli_gateway.manage_users set-password --email ana@example.com
    python -m intelli_gateway.manage_users disable --email ana@example.com  # ends her sessions
    python -m intelli_gateway.manage_users enable --email ana@example.com

The password is asked for twice (not echoed), or read from PLUSDAS_PASSWORD when that is set.
Use `make create-user` etc. from the repo root rather than calling this directly. The local admin
and demo accounts need none of this: the gateway creates them at startup (compose.yaml).
"""

import argparse
import asyncio
import getpass
import os
import sys
from datetime import UTC, datetime

from intelli_gateway.auth.service import AuthService
from intelli_gateway.config import load_settings
from intelli_gateway.schemas.users import ROLES, Role
from intelli_gateway.services.postgres.database import (
    create_database_engine,
    migrate,
    wait_for_database,
)
from intelli_gateway.services.postgres.user_store import PostgresUserStore
from intelli_gateway.utils.exceptions import GatewayError

PASSWORD_ENV = "PLUSDAS_PASSWORD"


def _password() -> str:
    from_env = os.environ.get(PASSWORD_ENV)
    if from_env:
        return from_env
    password = getpass.getpass("Password: ")
    if getpass.getpass("Repeat password: ") != password:
        raise SystemExit("the passwords don't match")
    return password


async def _run(args: argparse.Namespace) -> str:
    settings = load_settings()
    if settings.database_url is None:
        raise SystemExit("DATABASE_URL is not set: users are stored in this service's Postgres")
    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        await wait_for_database(engine)
        await migrate(engine)
        auth = AuthService(PostgresUserStore(engine), clock=lambda: datetime.now(UTC))
        if args.command == "create":
            role: Role = args.role
            user = await auth.create_user(
                args.email, args.display_name or args.email, role, _password()
            )
            return f"created {user.email} ({user.role})"
        if args.command == "set-password":
            user = await auth.set_password(args.email, _password())
            return f"password changed for {user.email}; their sessions were ended"
        if args.command in ("disable", "enable"):
            user = await auth.set_disabled(args.email, args.command == "disable")
            return f"{args.command}d {user.email}"
        raise SystemExit(f"unknown command {args.command}")
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Manage PlusDAS user accounts.")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="create a user")
    create.add_argument("--email", required=True)
    create.add_argument("--display-name", default="")
    create.add_argument("--role", choices=ROLES, default="engineer")
    for name in ("set-password", "disable", "enable"):
        commands.add_parser(name).add_argument("--email", required=True)
    args = parser.parse_args(argv)
    try:
        print(asyncio.run(_run(args)))  # noqa: T201 (CLI output)
    except GatewayError as error:
        raise SystemExit(f"error: {error}") from error


if __name__ == "__main__":
    sys.exit(main())
