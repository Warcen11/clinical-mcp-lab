import pytest
from clinical_mcp.client.validation import coerce

SCHEMA = {"type": "object", "required": ["age", "weight", "sex"], "properties": {
    "age": {"type": "integer", "minimum": 18, "maximum": 120},
    "weight": {"type": "number", "minimum": 20},
    "sex": {"type": "string", "enum": ["male", "female"]},
    "flag": {"type": "boolean"},
}}


def test_convert_types():
    result, _ = coerce(SCHEMA, {"age": "45", "weight": "80,5", "sex": "female", "flag": "да"})
    assert result == {"age": 45, "weight": 80.5, "sex": "female", "flag": True}


def test_required_not_invented():
    with pytest.raises(ValueError, match="Не подставляем"):
        coerce(SCHEMA, {"weight": 80, "sex": "male"})


def test_bad_integer():
    with pytest.raises(ValueError, match="целое"):
        coerce(SCHEMA, {"age": 18.5, "weight": 80, "sex": "male"})


def test_rejects_unknown():
    with pytest.raises(ValueError, match="Неизвестные"):
        coerce(SCHEMA, {"age": 30, "weight": 80, "sex": "male", "secret": "x"})


def test_rejects_nan():
    with pytest.raises(ValueError, match="конечным"):
        coerce(SCHEMA, {"age": 30, "weight": float("nan"), "sex": "male"})
