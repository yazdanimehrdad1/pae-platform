"""User accounts and login sessions (intelli-gateway owns PlusDAS users).

A session is a random opaque token in an HttpOnly cookie; only its SHA-256 is stored. Passwords
are scrypt hashes (auth/passwords.py). Times are timezone-aware UTC.
"""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

Role = Literal["engineer", "admin", "monitor"]
ROLES: tuple[Role, ...] = ("engineer", "admin", "monitor")

# The sign-in name is the email address, stored lower-case. A practical check, not RFC 5322:
# something@domain.tld, no spaces. Nothing is ever sent to it (yet).
EMAIL_PATTERN = r"^[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$"
EMAIL_MAX_LENGTH = 254

# Built-in accounts: these defaults are used locally; the cloud sets its own (deploy/cloud/config).
# `.local` is a reserved, non-routable domain: these are not mailboxes.
# The first admin of a fresh install (BOOTSTRAP_ADMIN_PASSWORD; the address is configurable).
BOOTSTRAP_ADMIN_EMAIL = "admin@plusdas.local"
# The shared demo account (DEMO_USER_PASSWORD; the address is DEMO_USER_EMAIL): many people use
# it, so nobody can change its password from inside it.
DEMO_EMAIL = "demo@plusdas.local"


class User(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    email: str
    display_name: str
    role: Role
    disabled: bool
    created_at: AwareDatetime
    last_login_at: AwareDatetime | None = None


class StoredUser(User):
    """A user with its password hash: only the auth service and the stores see this."""

    password_hash: str


class NewUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    email: str = Field(pattern=EMAIL_PATTERN, max_length=EMAIL_MAX_LENGTH)
    display_name: str = Field(min_length=1, max_length=200)
    role: Role
    password_hash: str


class UserSession(BaseModel):
    model_config = ConfigDict(frozen=True)

    token_hash: str
    user_id: int
    created_at: AwareDatetime
    expires_at: AwareDatetime
    last_seen_at: AwareDatetime
