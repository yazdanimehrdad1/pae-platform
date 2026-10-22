"""Test-only models for the standardized point link integration tests."""

from pydantic import BaseModel

from schemas.api_models import DevicePointResponse


class LinkedBess(BaseModel):
    """A BESS created through the API, its standardized points linked through the link endpoint."""

    site_id: int
    device_id: int
    power: DevicePointResponse  # NATIVE "W", in W
    soc: DevicePointResponse  # NATIVE "SoC", in %
    active_power: DevicePointResponse  # STANDARDIZED BESS_ACTIVE_POWER, as created
    state_of_charge: DevicePointResponse  # STANDARDIZED BESS_STATE_OF_CHARGE, as created
