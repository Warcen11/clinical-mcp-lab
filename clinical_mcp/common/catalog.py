"""Metadata returned by the stdio server via the MCP list_calculators tool."""
from clinical_mcp.common.calculators import REFERENCE

CALCULATORS = {
    "bmi": {
        "ru": "Индекс массы тела (BMI)", "domain": "Метаболизм",
        "method": "BMI = m / h², рост в метрах; интерпретация для взрослых",
        "parameters": {"weight_kg": "2–500 кг", "height_cm": "40–250 см"},
        "source": REFERENCE["bmi"],
    },
    "gcs": {
        "ru": "Шкала комы Глазго (GCS)", "domain": "Реанимация",
        "method": "GCS = E (1–4) + V (1–5) + M (1–6)",
        "parameters": {"eye": "1–4 балла", "verbal": "1–5 баллов", "motor": "1–6 баллов"},
        "source": REFERENCE["gcs"],
    },
    "creatinine_clearance": {
        "ru": "Клиренс креатинина Cockcroft–Gault", "domain": "Нефрология",
        "method": "CrCl = (140−возраст) × масса / (72 × креатинин [мг/дл]); для женщин ×0.85",
        "parameters": {"age_years": "18–120 лет", "weight_kg": "20–350 кг",
                       "creatinine_mg_dl": "0.2–20 мг/дл", "sex": "male/female"},
        "source": REFERENCE["creatinine_clearance"],
    },
}
