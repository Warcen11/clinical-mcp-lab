"""Schema-aware sanitizer with visible fallback values for local MCP tools."""
from __future__ import annotations

from typing import Any
import math


def unwrap_schema(schema: dict) -> dict:
    if "type" in schema:
        return schema
    for item in schema.get("anyOf", []):
        if item.get("type") != "null":
            return item
    return schema


# These are illustrative fallback values, not observations about a patient.
# The form shows each fallback inside the empty field before it can be used.
# Tools are separated by source, so stdio and SSE behave identically.
LOCAL_EXAMPLE_DEFAULTS: dict[str, dict[str, dict[str, Any]]] = {
    "stdio": {
        "bmi": {"weight_kg": 70.0, "height_cm": 170.0},
        "gcs": {"eye": 4, "verbal": 5, "motor": 6},
        "creatinine_clearance": {
            "age_years": 55, "weight_kg": 70.0,
            "creatinine_mg_dl": 1.0, "sex": "male",
        },
    },
    "sse": {
        "metabolic_bmi": {"weight_kg": 70.0, "height_cm": 170.0},
        "cardio_map": {"systolic": 120, "diastolic": 80},
        "cardio_cha2ds2_vasc": {
            "age_years": 55, "sex": "male", "heart_failure": False,
            "hypertension": False, "diabetes": False,
            "stroke_or_tia": False, "vascular_disease": False,
        },
        "nephro_creatinine_clearance": {
            "age_years": 55, "weight_kg": 70.0,
            "creatinine_mg_dl": 1.0, "sex": "male",
        },
        "critical_gcs": {"eye": 4, "verbal": 5, "motor": 6},
        "critical_qsofa": {
            "respiratory_rate": 16, "systolic": 120,
            "altered_mental_status": False,
        },
    },
}


def local_defaults(source: str, tool_name: str) -> dict[str, Any]:
    """Return advertised defaults for a single local MCP tool, or none for remote."""
    return LOCAL_EXAMPLE_DEFAULTS.get(source, {}).get(tool_name, {})


def display_default(value: Any) -> str:
    """Consistent short label for Streamlit placeholders/help."""
    if isinstance(value, bool):
        return "Да" if value else "Нет"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def coerce(
    schema: dict,
    arguments: dict[str, Any],
    *,
    smart_defaults: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    result: dict = {}
    warnings: list[str] = []
    for key, meta in properties.items():
        value = arguments.get(key)
        if value is None or value == "":
            if smart_defaults is not None and key in smart_defaults:
                value = smart_defaults[key]
                warnings.append(f"Подставлено по умолчанию: «{key}» = {display_default(value)}")
            elif key in required:
                raise ValueError(f"Поле «{key}» обязательно. Значение по умолчанию не задано.")
            else:
                continue
        real = unwrap_schema(meta)
        expected = real.get("type", "string")
        try:
            if expected == "integer":
                number = float(str(value).replace(",", "."))
                if not number.is_integer():
                    raise ValueError("ожидается целое число")
                value = int(number)
            elif expected == "number":
                value = float(str(value).replace(",", "."))
            elif expected == "boolean":
                if type(value) is bool:
                    pass
                elif str(value).lower() in ("true", "1", "да"):
                    value = True
                elif str(value).lower() in ("false", "0", "нет"):
                    value = False
                else:
                    raise ValueError("ожидается true/false")
            elif expected == "string":
                value = str(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Поле «{key}»: {exc}") from exc
        if expected in {"integer", "number"}:
            if not math.isfinite(value):
                raise ValueError(f"{key}: число должно быть конечным")
            if "minimum" in real and value < real["minimum"]:
                raise ValueError(f"{key}: значение ниже минимума {real['minimum']}")
            if "maximum" in real and value > real["maximum"]:
                raise ValueError(f"{key}: значение выше максимума {real['maximum']}")
        if "enum" in real and value not in real["enum"]:
            raise ValueError(f"{key}: допустимые значения {real['enum']}")
        if key in arguments and arguments[key] is not None and arguments[key] != "" and value != arguments[key]:
            warnings.append(f"{key}: тип приведён к {expected}")
        result[key] = value
    additional = set(arguments) - set(properties)
    if additional:
        raise ValueError(f"Неизвестные параметры: {', '.join(sorted(additional))}")
    return result, warnings
