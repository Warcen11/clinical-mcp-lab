"""User-visible sanitization. Never substitute fabricated clinical measurements."""
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


def coerce(schema: dict, arguments: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    result: dict = {}
    warnings: list[str] = []
    for key, meta in properties.items():
        value = arguments.get(key)
        if value is None or value == "":
            if key in required:
                raise ValueError(f"Поле «{key}» обязательно. Не подставляем вымышленные медицинские данные.")
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
        if value != arguments[key]:
            warnings.append(f"{key}: тип приведён к {expected}")
        result[key] = value
    additional = set(arguments) - set(properties)
    if additional:
        raise ValueError(f"Неизвестные параметры: {', '.join(sorted(additional))}")
    return result, warnings
