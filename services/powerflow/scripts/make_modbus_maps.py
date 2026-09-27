"""(Re)generate the default Modbus maps shipped in site_config/modbus_maps/<site>/, for every
asset (BESS, PV, load, POI meter, site status) of every default site in site_config/sites/.
Overwrites the default map files. The database is not touched: load them into it with
POST /api/defaults/restore (overwrite=true replaces stored maps).

Usage: uv run python scripts/make_modbus_maps.py

The layout comes from `powerflow.points.modbus_map.default_site_maps`: unit IDs from 1 in the
order BESS, PV, loads, meter, site status; setpoints in holding registers from 0; measurements in
input registers from 0; nameplate in input registers from 100.
"""

import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT / "src"))

from powerflow.points.modbus_map import default_site_maps  # noqa: E402
from powerflow.site_config import SiteConfig  # noqa: E402

DEFAULTS_DIR = SERVICE_ROOT / "site_config"


def main() -> None:
    for site_file in sorted((DEFAULTS_DIR / "sites").glob("*.json")):
        config = SiteConfig.model_validate_json(site_file.read_text(encoding="utf-8"))
        maps_dir = DEFAULTS_DIR / "modbus_maps" / site_file.stem
        maps_dir.mkdir(parents=True, exist_ok=True)
        maps = default_site_maps(config)
        for modbus_map in maps:
            path = maps_dir / f"{modbus_map.asset}.json"
            with path.open("w", encoding="utf-8", newline="\n") as map_file:
                map_file.write(
                    modbus_map.model_dump_json(indent=2, exclude_unset=True, exclude_none=True)
                    + "\n"
                )
        print(f"{site_file.stem}: {len(maps)} maps ({', '.join(item.asset for item in maps)})")


if __name__ == "__main__":
    main()
