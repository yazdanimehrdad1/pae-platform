"""CSV time-series profiles (load, PV availability) with linear interpolation."""

from powerflow.profiles.profile import (
    Profile,
    ProfileKind,
    load_profile_file,
    parse_profile_csv,
)

__all__ = ["Profile", "ProfileKind", "load_profile_file", "parse_profile_csv"]
