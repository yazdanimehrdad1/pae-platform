"""The default sites as the data migration inserts them (migrations/0003_default_sites.sql).

The database is the only store for sites; this module only reads the migration file, so code that
has no database (the in-memory repository for tests, the Postman example) starts from exactly the
sites a freshly migrated Postgres has. Runtime with Postgres never uses it.
"""

import re
from functools import cache
from pathlib import Path

from powerflow.errors import SiteConfigError
from powerflow.site_config import SiteConfig

SEED_MIGRATION = Path(__file__).resolve().parent / "migrations" / "0003_default_sites.sql"
_SITE = re.compile(
    r"INSERT INTO sites \(name, config\) VALUES \('([^']+)', \$site\$(.*?)\$site\$", re.S
)
_ACTIVE = re.compile(r"'active_site', '\{\"site\": \"([^\"]+)\"\}'")


@cache
def _migration_text() -> str:
    return SEED_MIGRATION.read_text(encoding="utf-8")


def default_sites() -> dict[str, SiteConfig]:
    """name → config of every site the migration inserts."""
    sites = {
        name: SiteConfig.model_validate_json(document)
        for name, document in _SITE.findall(_migration_text())
    }
    if not sites:
        raise SiteConfigError(f"{SEED_MIGRATION.name} inserts no sites")
    return sites


def default_active_site() -> str:
    match = _ACTIVE.search(_migration_text())
    if match is None:
        raise SiteConfigError(f"{SEED_MIGRATION.name} sets no active site")
    return match.group(1)
