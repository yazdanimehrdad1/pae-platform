"""The user-admin CLI's guard: accounts live in this service's Postgres, so without DATABASE_URL
it stops before doing anything (the local admin and demo accounts come from startup, not here).

Invariant guarded: no DATABASE_URL = a clear exit, never an account that would vanish.
"""

import pytest
from fakes import make_settings

from intelli_gateway import manage_users


def test_refuses_without_a_database(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = make_settings()
    monkeypatch.setattr(manage_users, "load_settings", lambda: settings)
    with pytest.raises(SystemExit, match="DATABASE_URL"):
        manage_users.main(["set-password", "--email", "ana@example.com"])
