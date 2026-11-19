"""Run: python -m clinical_mcp.network.server ; SSE on http://127.0.0.1:8000/sse."""
import logging
from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from clinical_mcp.common import calculators as calc

logging.basicConfig(level=logging.INFO)
mcp = MCPServer("clinical-network-sse", version="0.1.0")


def _safe(function, *args):
    try:
        return function(*args)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def metabolic_bmi(weight_kg: Annotated[float, Field(ge=2, le=500)],
                  height_cm: Annotated[float, Field(ge=40, le=250)]) -> dict:
    """Метаболизм — BMI (индекс массы тела)."""
    return _safe(calc.bmi, weight_kg, height_cm)


@mcp.tool()
def cardio_map(systolic: Annotated[int, Field(ge=40, le=300, description="САД, мм рт. ст.")],
               diastolic: Annotated[int, Field(ge=20, le=200, description="ДАД, мм рт. ст.")]) -> dict:
    """Кардиология — среднее артериальное давление, MAP."""
    return _safe(calc.cardio_map, systolic, diastolic)


@mcp.tool()
def cardio_cha2ds2_vasc(
        age_years: Annotated[int, Field(ge=18, le=120)],
        sex: Literal["male", "female"],
        heart_failure: bool, hypertension: bool, diabetes: bool,
        stroke_or_tia: bool, vascular_disease: bool) -> dict:
    """Кардиология — CHA2DS2-VASc, факторы риска инсульта при фибрилляции предсердий."""
    return _safe(calc.cardio_cha2ds2_vasc, age_years, sex, heart_failure,
                 hypertension, diabetes, stroke_or_tia, vascular_disease)


@mcp.tool()
def nephro_creatinine_clearance(
        age_years: Annotated[int, Field(ge=18, le=120)],
        weight_kg: Annotated[float, Field(ge=20, le=350)],
        creatinine_mg_dl: Annotated[float, Field(ge=0.2, le=20)],
        sex: Literal["male", "female"]) -> dict:
    """Нефрология — Cockcroft–Gault; клиренс креатинина (не eGFR)."""
    return _safe(calc.creatinine_clearance, age_years, weight_kg, creatinine_mg_dl, sex)


@mcp.tool()
def critical_gcs(eye: Annotated[int, Field(ge=1, le=4)],
                 verbal: Annotated[int, Field(ge=1, le=5)],
                 motor: Annotated[int, Field(ge=1, le=6)]) -> dict:
    """Реанимация — шкала комы Глазго (GCS)."""
    return _safe(calc.gcs, eye, verbal, motor)


@mcp.tool()
def critical_qsofa(respiratory_rate: Annotated[int, Field(ge=4, le=80, description="ЧДД в минуту")],
                   systolic: Annotated[int, Field(ge=40, le=300, description="САД, мм рт. ст.")],
                   altered_mental_status: bool) -> dict:
    """Реанимация — qSOFA; оценка риска при подозрении на инфекцию."""
    return _safe(calc.critical_qsofa, respiratory_rate, systolic, altered_mental_status)


if __name__ == "__main__":
    # Legacy SSE is explicitly required by the assignment; not the recommended
    # transport for new production systems (Streamable HTTP supersedes SSE).
    mcp.run(transport="sse", host="127.0.0.1", port=8000,
            sse_path="/sse", message_path="/messages")
