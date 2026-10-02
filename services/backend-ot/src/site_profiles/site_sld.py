"""
Loading a profile's single line diagram (individual_sites/<key>/sld.json).

A profile calls load_site_sld when it is imported, so a missing or invalid sld.json stops the
app from starting instead of failing on a request. The format is SiteSld
(schemas/site_profiles/single_line_diagram.py).
"""

from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from schemas.site_profiles import SiteSld
from utils.exceptions import SiteProfileConfigError


def load_site_sld(path: Path) -> SiteSld:
    """Read and validate a profile's sld.json."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise SiteProfileConfigError(f"Cannot read single line diagram {path}: {e}") from e
    try:
        return SiteSld.model_validate_json(raw)
    except PydanticValidationError as e:
        raise SiteProfileConfigError(f"Invalid single line diagram {path}:\n{e}") from e
