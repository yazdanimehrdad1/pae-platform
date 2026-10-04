"""Typed exceptions. Adapters map them to protocol errors (the HTTP adapter: status codes)."""


class PowerflowError(Exception):
    """Base class for every error this service raises on purpose."""


class SiteConfigError(PowerflowError):
    """The site config file can't be read or parsed, or references something invalid."""


class ProfileError(PowerflowError):
    """A profile CSV is missing, malformed or has the wrong columns."""


class UnknownAssetError(PowerflowError):
    """No asset of that type has that id."""


class UnknownPointError(PowerflowError):
    """No point has that name."""


class PointAccessError(PowerflowError):
    """The point exists but can't be written (read-only), or can't be read (write-only)."""


class SetpointError(PowerflowError):
    """A setpoint is invalid (not merely out of range: out-of-range values are clamped)."""


class InvalidStateError(PowerflowError):
    """The request isn't allowed in the simulation's current state."""


class NotInTestModeError(InvalidStateError):
    """Manual stepping is only allowed with `simulation.test_mode: true`."""


class NoMeasurementError(InvalidStateError):
    """No simulation step has run yet, so there is no measurement to return."""


class NonConvergenceError(PowerflowError):
    """The power flow didn't converge."""


class NotFoundError(PowerflowError):
    """A stored site, Modbus map or profile scenario doesn't exist."""


class InvalidNameError(PowerflowError):
    """A site/map/scenario name isn't allowed (bad characters, or it would leave its folder)."""


class InUseError(InvalidStateError):
    """The item can't change now because it's in use (e.g. deleting the active site)."""


class ProtectedSiteError(InvalidStateError):
    """A default site (it ships with powerflow) can't be deleted."""


class PointStandardError(PowerflowError):
    """The point-standard CSVs are invalid, or a site doesn't fit the Modbus register layout."""
