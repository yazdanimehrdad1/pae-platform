"""Unit tests for schemas.db_models.column_types.VirtualDefinitionJSON.

Invariant guarded: device_points.virtual_definition round-trips as a typed definition model; a
malformed definition is refused on write; a stored value that no longer parses loads as None
(the point computes nothing) instead of failing every query that loads the row.
"""

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from schemas.api_models import (
    VirtualCalculationDefinition,
    VirtualCase,
    VirtualCondition,
    VirtualConditionDefinition,
    VirtualConditionGroup,
)
from schemas.db_models.column_types import VirtualDefinitionJSON

DIALECT = postgresql.dialect()
COLUMN = VirtualDefinitionJSON()
CALCULATION = VirtualCalculationDefinition(kind="calculation", function="ratio", inputs=[1, 2], scale=100)
CONDITION = VirtualConditionDefinition(
    kind="condition",
    cases=[VirtualCase(output=1, label="on", when=VirtualConditionGroup(match="all", items=[
        VirtualCondition(point_id=3, operator="bit_set", bit=2),
    ]))],
)


class TestWrite:
    @pytest.mark.parametrize("definition", [CALCULATION, CONDITION])
    def test_a_model_is_stored_as_its_json(self, definition):
        assert COLUMN.process_bind_param(definition, DIALECT) == definition.model_dump(mode="json")

    def test_a_valid_dict_is_accepted_and_normalised(self):
        stored = COLUMN.process_bind_param({"kind": "calculation", "function": "sum", "inputs": [1]}, DIALECT)
        assert stored == {"kind": "calculation", "function": "sum", "inputs": [1], "scale": 1.0, "offset": 0.0}

    def test_a_malformed_definition_is_refused(self):
        with pytest.raises(ValidationError):
            COLUMN.process_bind_param({"kind": "calculation", "function": "ratio", "inputs": [1]}, DIALECT)

    def test_none_is_sql_null_not_json_null(self):
        # Regression: JSON's default writes None as the JSON literal null, which the
        # chk_device_points_virtual_definition_category constraint rejects on non-virtual points.
        assert COLUMN.process_bind_param(None, DIALECT) is None
        assert COLUMN.impl.none_as_null is True


class TestRead:
    @pytest.mark.parametrize("definition", [CALCULATION, CONDITION])
    def test_round_trip_gives_the_same_model(self, definition):
        stored = COLUMN.process_bind_param(definition, DIALECT)
        assert COLUMN.process_result_value(stored, DIALECT) == definition

    def test_a_stored_value_that_no_longer_parses_loads_as_none(self):
        assert COLUMN.process_result_value({"kind": "nonsense"}, DIALECT) is None

    def test_null_loads_as_none(self):
        assert COLUMN.process_result_value(None, DIALECT) is None
