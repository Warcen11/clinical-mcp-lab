import pytest
from clinical_mcp.client.validation import LOCAL_EXAMPLE_DEFAULTS, local_defaults, display_default, coerce

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
    with pytest.raises(ValueError, match="по умолчанию не задано"):
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


def test_missing_values_use_visible_local_defaults_and_are_reported():
    demo = {"age": 55, "weight": 70.0, "sex": "male"}
    result, warnings = coerce(
        SCHEMA, {"age": "40", "weight": None, "sex": None}, smart_defaults=demo
    )
    assert result["age"] == 40  # User value must win over demo example.
    assert result["weight"] == 70.0
    assert result["sex"] == "male"
    assert len([message for message in warnings if message.startswith("Подставлено по умолчанию")]) == 2


def test_smart_defaults_do_not_repair_invalid_values():
    demo = {"age": 55, "weight": 70.0, "sex": "male"}
    with pytest.raises(ValueError, match="ниже минимума"):
        coerce(SCHEMA, {"age": 12, "weight": None, "sex": None}, smart_defaults=demo)


def test_all_local_tools_have_defaults():
    assert set(LOCAL_EXAMPLE_DEFAULTS) == {"stdio", "sse"}
    assert len(LOCAL_EXAMPLE_DEFAULTS["stdio"]) == 3
    assert len(LOCAL_EXAMPLE_DEFAULTS["sse"]) == 6
    for source, tools in LOCAL_EXAMPLE_DEFAULTS.items():
        for tool_name, defaults in tools.items():
            assert local_defaults(source, tool_name) == defaults
            assert defaults, f"{source}/{tool_name}"
    assert local_defaults("remote", "pubmed_search_articles") == {}
    assert local_defaults("stdio", "list_calculators") == {}


def test_stdio_gcs_uses_same_fallback_mechanism_as_sse():
    props = {name: {"type": "integer", "minimum": minimum, "maximum": maximum}
             for name, minimum, maximum in [("eye", 1, 4), ("verbal", 1, 5), ("motor", 1, 6)]}
    schema = {"type": "object", "required": list(props), "properties": props}
    for source, name in [("stdio", "gcs"), ("sse", "critical_gcs")]:
        result, messages = coerce(schema, {"eye": None, "verbal": None, "motor": None},
                                  smart_defaults=local_defaults(source, name))
        assert result == {"eye": 4, "verbal": 5, "motor": 6}
        assert len(messages) == 3


def test_explicit_values_take_precedence_for_both_transports():
    schema = {"type": "object", "required": ["weight_kg", "height_cm"], "properties": {
        "weight_kg": {"type": "number", "minimum": 2, "maximum": 500},
        "height_cm": {"type": "number", "minimum": 40, "maximum": 250},
    }}
    for source, name in [("stdio", "bmi"), ("sse", "metabolic_bmi")]:
        result, warnings = coerce(schema, {"weight_kg": 80, "height_cm": None},
                                  smart_defaults=local_defaults(source, name))
        assert result == {"weight_kg": 80.0, "height_cm": 170.0}
        assert len(warnings) == 1
        assert "height_cm" in warnings[0]


def test_formatted_defaults():
    assert display_default(70.0) == "70"
    assert display_default(1.5) == "1.5"
    assert display_default(False) == "Нет"
    assert display_default(True) == "Да"


def test_missing_required_fields_without_mapped_local_default_still_raise():
    with pytest.raises(ValueError, match="обязательно"):
        coerce(SCHEMA, {"weight": None, "sex": "male"})
