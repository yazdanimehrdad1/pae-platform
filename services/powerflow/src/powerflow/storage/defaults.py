"""The shipped defaults in site_config/: read-only seed data for the database.

```
<root>/active.json                                {"site": "<name>"}: the default active site
<root>/sites/<name>.json                          SiteConfig
<root>/modbus_maps/<site>/<asset_type>.<id>.json  ModbusMap
```
Nothing here is written at runtime: the database is the only store for sites, maps and the
active site. (Profiles are separate: see ProfileStore.)
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError

from powerflow.errors import SiteConfigError
from powerflow.points.modbus_map import ModbusMap
from powerflow.site_config import SiteConfig

ModelType = TypeVar("ModelType", SiteConfig, ModbusMap)


@dataclass(frozen=True)
class DefaultSite:
    name: str
    config: SiteConfig
    maps: dict[str, ModbusMap] = field(default_factory=dict)


@dataclass(frozen=True)
class Defaults:
    active_site: str
    sites: list[DefaultSite]


def read_defaults(root: Path) -> Defaults:
    """Read and validate every default site and map. Raises SiteConfigError on a bad file."""
    sites: list[DefaultSite] = []
    for site_file in sorted((root / "sites").glob("*.json")):
        name = site_file.stem
        maps = {
            map_file.stem: _load(map_file, ModbusMap)
            for map_file in sorted((root / "modbus_maps" / name).glob("*.json"))
        }
        sites.append(DefaultSite(name=name, config=_load(site_file, SiteConfig), maps=maps))
    active_file = root / "active.json"
    try:
        active_site = json.loads(active_file.read_text(encoding="utf-8"))["site"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise SiteConfigError(f'{active_file} must look like {{"site": "<name>"}}') from error
    if active_site not in {site.name for site in sites}:
        raise SiteConfigError(f"default active site {active_site!r} isn't in {root / 'sites'}")
    return Defaults(active_site=active_site, sites=sites)


def _load(path: Path, model: type[ModelType]) -> ModelType:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as error:
        raise SiteConfigError(f"invalid default {path}:\n{error}") from error
