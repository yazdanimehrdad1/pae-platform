"""CSV time-series profiles (load, PV availability) with linear interpolation."""

from powerflow.profiles.profile import (
    Profile,
    ProfileKind,
    epoch_seconds,
    load_profile_file,
    parse_profile_csv,
)

__all__ = ["Profile", "ProfileKind", "epoch_seconds", "load_profile_file", "parse_profile_csv"]
