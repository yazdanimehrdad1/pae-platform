"""Auto-generation of STANDARDIZED points for a device based on its type."""

from pydantic import BaseModel

from schemas.api_models import DevicePointData, DeviceType, PointClass


class StandardizedPointTemplate(BaseModel):
    name: str
    address: int
    point_class: PointClass = "ANALOG"


class DeviceStandardizedPoints(BaseModel):
    device_type: DeviceType
    points: list[StandardizedPointTemplate]


_STANDARDIZED_POINTS: dict[str, DeviceStandardizedPoints] = {
    "BESS": DeviceStandardizedPoints(
        device_type="BESS",
        points=[
            StandardizedPointTemplate(name="BESS_ACTIVE_POWER", address=0),
            StandardizedPointTemplate(name="BESS_STATE_OF_CHARGE", address=1),
            StandardizedPointTemplate(name="BESS_STATUS", address=2, point_class="BINARY"),
        ],
    ),
    "ES": DeviceStandardizedPoints(
        device_type="ES",
        points=[
            StandardizedPointTemplate(name="ES_ACTIVE_POWER", address=0),
            StandardizedPointTemplate(name="ES_REACTIVE_POWER", address=1),
            StandardizedPointTemplate(name="ES_STATUS", address=2, point_class="BINARY"),
        ],
    ),
    "INVERTER": DeviceStandardizedPoints(
        device_type="INVERTER",
        points=[
            StandardizedPointTemplate(name="INVERTER_ACTIVE_POWER", address=0),
            StandardizedPointTemplate(name="INVERTER_DC_VOLTAGE", address=1),
            StandardizedPointTemplate(name="INVERTER_STATUS", address=2, point_class="BINARY"),
        ],
    ),
    "PV": DeviceStandardizedPoints(
        device_type="PV",
        points=[
            StandardizedPointTemplate(name="PV_ACTIVE_POWER", address=0),
            StandardizedPointTemplate(name="PV_DC_CURRENT", address=1),
            StandardizedPointTemplate(name="PV_STATUS", address=2, point_class="BINARY"),
        ],
    ),
    "GENERATOR": DeviceStandardizedPoints(
        device_type="GENERATOR",
        points=[
            StandardizedPointTemplate(name="GENERATOR_ACTIVE_POWER", address=0),
            StandardizedPointTemplate(name="GENERATOR_FREQUENCY", address=1),
            StandardizedPointTemplate(name="GENERATOR_STATUS", address=2, point_class="BINARY"),
        ],
    ),
    "LOADBANK": DeviceStandardizedPoints(
        device_type="LOADBANK",
        points=[
            StandardizedPointTemplate(name="LOADBANK_ACTIVE_POWER", address=0),
            StandardizedPointTemplate(name="LOADBANK_CURRENT", address=1),
            StandardizedPointTemplate(name="LOADBANK_STATUS", address=2, point_class="BINARY"),
        ],
    ),
    "RELAY": DeviceStandardizedPoints(
        device_type="RELAY",
        points=[
            StandardizedPointTemplate(name="RELAY_POSITION", address=0, point_class="BINARY"),
            StandardizedPointTemplate(name="RELAY_CURRENT", address=1),
            StandardizedPointTemplate(name="RELAY_STATUS", address=2, point_class="BINARY"),
        ],
    ),
    "IED": DeviceStandardizedPoints(
        device_type="IED",
        points=[
            StandardizedPointTemplate(name="IED_ACTIVE_POWER", address=0),
            StandardizedPointTemplate(name="IED_VOLTAGE", address=1),
            StandardizedPointTemplate(name="IED_STATUS", address=2, point_class="BINARY"),
        ],
    ),
}


def generate_standardized_points(
    device_type: DeviceType,
    device_id: int,
    site_id: int,
) -> list[DevicePointData]:
    """
    Return a list of STANDARDIZED DevicePointData for the given device type.
    Returns an empty list if the device type has no defined standardized points.
    """
    definition = _STANDARDIZED_POINTS.get(device_type.upper())
    if definition is None:
        return []
    return [
        DevicePointData(
            site_id=site_id,
            device_id=device_id,
            address=point.address,
            name=point.name,
            size=1,
            data_type="uint16",
            category="STANDARDIZED",
            point_class=point.point_class,
        )
        for point in definition.points
    ]
