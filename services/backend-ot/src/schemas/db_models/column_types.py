"""Custom column types: JSON columns whose content is a Pydantic model.

The database column stays plain JSON(B); these types convert the model to JSON on write and back
to the model on read, so ORM code works with typed models instead of dicts.
"""

from typing import Any, ClassVar

from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import JSON
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

from logger import get_logger
from schemas.api_models.alarms import AlarmRule, UserAlarmRule
from schemas.api_models.single_line_diagram import SiteSld
from schemas.api_models.virtual_points import VirtualDefinition, VirtualPointDefinition

logger = get_logger(__name__)


class PydanticJSON(TypeDecorator[Any]):
    """A JSON column holding one Pydantic model (or a discriminated union of models).

    Subclasses set `adapter`. Writes validate (a dict is accepted and checked too), so a malformed
    value never reaches the database through the ORM. A stored value that no longer parses (e.g.
    edited by hand in SQL) loads as None with a warning, so one bad row doesn't break every query
    that loads it. None is SQL NULL, not the JSON literal null, so IS NULL checks hold.
    """

    impl = JSON
    cache_ok = True
    adapter: ClassVar[TypeAdapter[Any]]
    column_name: ClassVar[str]

    def __init__(self) -> None:
        super().__init__(none_as_null=True)

    def process_bind_param(self, value: object, dialect: Dialect) -> object:
        if value is None:
            return None
        return self.adapter.dump_python(self.adapter.validate_python(value), mode="json")

    def process_result_value(self, value: object, dialect: Dialect) -> object:
        if value is None:
            return None
        try:
            return self.adapter.validate_python(value)
        except PydanticValidationError as error:
            logger.warning("stored %s does not parse, treated as none: %s", self.column_name, error)
            return None


class VirtualDefinitionJSON(PydanticJSON):
    """`device_points.virtual_definition`: a VirtualConditionDefinition or VirtualCalculationDefinition."""

    adapter: ClassVar[TypeAdapter[VirtualDefinition]] = TypeAdapter(VirtualPointDefinition)
    column_name = "device_points.virtual_definition"


class AlarmRuleJSON(PydanticJSON):
    """`alarm_definitions.rule`: a ThresholdAlarm, CommsStaleAlarm or ConditionAlarm."""

    adapter: ClassVar[TypeAdapter[UserAlarmRule]] = TypeAdapter(AlarmRule)
    column_name = "alarm_definitions.rule"


class SiteSldJSON(PydanticJSON):
    """`site_slds.document`: a SiteSld."""

    adapter: ClassVar[TypeAdapter[SiteSld]] = TypeAdapter(SiteSld)
    column_name = "site_slds.document"
