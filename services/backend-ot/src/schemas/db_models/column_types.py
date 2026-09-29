"""Custom column types: JSON columns whose content is a Pydantic model.

The database column stays plain JSON(B); these types convert the model to JSON on write and back
to the model on read, so ORM code works with typed models instead of dicts.
"""

from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import JSON
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

from logger import get_logger
from schemas.api_models.virtual_points import VirtualDefinition, VirtualPointDefinition

logger = get_logger(__name__)

_virtual_definition_adapter: TypeAdapter[VirtualDefinition] = TypeAdapter(VirtualPointDefinition)


class VirtualDefinitionJSON(TypeDecorator[VirtualDefinition]):
    """`device_points.virtual_definition`: a VirtualConditionDefinition or VirtualCalculationDefinition.

    Writes validate (a dict is accepted and checked too), so a malformed definition never reaches
    the database through the ORM. A stored value that no longer parses (e.g. edited by hand in
    SQL) loads as None with a warning, so the point computes nothing instead of breaking every
    query that loads it.
    """

    impl = JSON
    cache_ok = True

    def __init__(self) -> None:
        # None must be SQL NULL, not the JSON literal null: the CHECK allows a definition only
        # on VIRTUAL points, and 'null'::jsonb counts as one.
        super().__init__(none_as_null=True)

    def process_bind_param(self, value: object, dialect: Dialect) -> object:
        if value is None:
            return None
        definition = _virtual_definition_adapter.validate_python(value)
        return _virtual_definition_adapter.dump_python(definition, mode="json")

    def process_result_value(self, value: object, dialect: Dialect) -> VirtualDefinition | None:
        if value is None:
            return None
        try:
            return _virtual_definition_adapter.validate_python(value)
        except PydanticValidationError as error:
            logger.warning("stored virtual_definition does not parse, treated as none: %s", error)
            return None
