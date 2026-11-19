"""Run: python -m clinical_mcp.stdio.server (stdout belongs to MCP)."""
import logging
from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from clinical_mcp.common import calculators as calc
from clinical_mcp.common.catalog import CALCULATORS

logging.basicConfig(level=logging.INFO)  # stderr, not stdout
mcp = MCPServer("clinical-stdio", version="0.1.0")


def _safe(function, *args):
    try:
        return function(*args)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def bmi(weight_kg: Annotated[float, Field(ge=2, le=500, description="Масса тела, кг")],
        height_cm: Annotated[float, Field(ge=40, le=250, description="Рост, см")]) -> dict:
    """Индекс массы тела; BMI; формула для взрослых."""
    return _safe(calc.bmi, weight_kg, height_cm)


@mcp.tool()
def gcs(eye: Annotated[int, Field(ge=1, le=4, description="Открывание глаз (1–4)")],
        verbal: Annotated[int, Field(ge=1, le=5, description="Речевая реакция (1–5)")],
        motor: Annotated[int, Field(ge=1, le=6, description="Двигательная реакция (1–6)")]) -> dict:
    """Шкала комы Глазго, Glasgow Coma Scale (GCS)."""
    return _safe(calc.gcs, eye, verbal, motor)


@mcp.tool()
def creatinine_clearance(
        age_years: Annotated[int, Field(ge=18, le=120, description="Возраст, лет")],
        weight_kg: Annotated[float, Field(ge=20, le=350, description="Масса тела, кг")],
        creatinine_mg_dl: Annotated[float, Field(ge=0.2, le=20, description="Креатинин крови, мг/дл (НЕ мкмоль/л)")],
        sex: Literal["male", "female"]) -> dict:
    """Клиренс креатинина Cockcroft–Gault, CrCl (не CKD-EPI)."""
    return _safe(calc.creatinine_clearance, age_years, weight_kg, creatinine_mg_dl, sex)


@mcp.tool()
def list_calculators() -> dict:
    """Метаданные локальных калькуляторов: методики, единицы, допустимые границы, ссылки."""
    return CALCULATORS


if __name__ == "__main__":
    mcp.run(transport="stdio")
