"""Pure educational calculators. No treatment decisions and no private patient data.

Clinical scores simplify reality and require professional context; calculations here
are intentionally transparent and independent of MCP so they can be unit-tested.
The servers expose them to the UI *only* over MCP, never through direct imports.
"""
from __future__ import annotations

from typing import Any

REFERENCE = {
    "bmi": "https://www.who.int/data/gho/data/themes/topics/topic-details/GHO/body-mass-index",
    "gcs": "https://pubmed.ncbi.nlm.nih.gov/4136544/",
    "creatinine_clearance": "https://pubmed.ncbi.nlm.nih.gov/1244564/",
    "cardio_map": "https://www.ncbi.nlm.nih.gov/books/NBK538226/",
    "cardio_cha2ds2_vasc": "https://doi.org/10.1378/chest.09-1584",
    "critical_qsofa": "https://doi.org/10.1001/jama.2016.0288",
}


def _range(label: str, value: float, lo: float, hi: float) -> None:
    if not lo <= value <= hi:
        raise ValueError(f"{label}: допустимый диапазон {lo:g}–{hi:g}, получено {value:g}.")


def _output(value: float | int, unit: str, interpretation: str, reference: str,
            components: dict[str, Any], risk: str = "info", warnings: list[str] | None = None) -> dict:
    return {
        "value": value,
        "unit": unit,
        "risk": risk,
        "interpretation": interpretation,
        "components": components,
        "warnings": warnings or [],
        "source": REFERENCE[reference],
        "educational_only": True,
    }


def bmi(weight_kg: float, height_cm: float) -> dict:
    _range("Масса (кг)", weight_kg, 2, 500)
    _range("Рост (см)", height_cm, 40, 250)
    score = round(weight_kg / (height_cm / 100) ** 2, 2)
    if score < 18.5:
        label, risk = "Дефицит массы тела по классификации BMI для взрослых", "warning"
    elif score < 25:
        label, risk = "Диапазон BMI, соответствующий нормальной массе тела взрослого", "low"
    elif score < 30:
        label, risk = "Избыточная масса тела по BMI", "warning"
    else:
        label, risk = "Ожирение по BMI (классификация для взрослых)", "high"
    return _output(score, "кг/м²", label, "bmi", {"weight_kg": weight_kg, "height_cm": height_cm}, risk)


def gcs(eye: int, verbal: int, motor: int) -> dict:
    _range("Открывание глаз", eye, 1, 4)
    _range("Речевая реакция", verbal, 1, 5)
    _range("Двигательная реакция", motor, 1, 6)
    total = eye + verbal + motor
    if total <= 8:
        label, risk = "Тяжёлое нарушение сознания по суммарной GCS", "high"
    elif total <= 12:
        label, risk = "Умеренное нарушение сознания по суммарной GCS", "warning"
    else:
        label, risk = "Лёгкое нарушение / сохранённое сознание по суммарной GCS", "low"
    return _output(total, "баллов из 15", label, "gcs",
                   {"eye": eye, "verbal": verbal, "motor": motor}, risk,
                   ["Шкала GCS требует очного обследования; отдельные компоненты важнее одного итога."])


def creatinine_clearance(age_years: int, weight_kg: float, creatinine_mg_dl: float, sex: str) -> dict:
    _range("Возраст", age_years, 18, 120)
    _range("Масса (кг)", weight_kg, 20, 350)
    _range("Креатинин (мг/дл)", creatinine_mg_dl, 0.2, 20)
    if sex not in ("male", "female"):
        raise ValueError("sex должен быть 'male' или 'female'.")
    multiplier = 0.85 if sex == "female" else 1.0
    value = round(((140 - age_years) * weight_kg * multiplier) / (72 * creatinine_mg_dl), 1)
    return _output(value, "мл/мин", "Оценка клиренса креатинина по формуле Cockcroft–Gault", "creatinine_clearance",
                   {"age_years": age_years, "weight_kg": weight_kg,
                    "creatinine_mg_dl": creatinine_mg_dl, "sex": sex}, "info",
                   ["Это не eGFR (CKD-EPI). Формула зависит от выбранной массы тела и имеет ограничения.",
                    "Не используйте число для назначения доз без клинической проверки."])


def cardio_map(systolic: int, diastolic: int) -> dict:
    _range("Систолическое давление", systolic, 40, 300)
    _range("Диастолическое давление", diastolic, 20, 200)
    if diastolic >= systolic:
        raise ValueError("Диастолическое давление должно быть меньше систолического.")
    value = round((systolic + 2 * diastolic) / 3, 1)
    return _output(value, "мм рт. ст.", "Приближённое среднее артериальное давление (MAP)", "cardio_map",
                   {"systolic": systolic, "diastolic": diastolic},
                   "warning" if value < 65 else "info",
                   ["MAP по формуле является приближением, особенно при изменении ЧСС и нестабильной гемодинамике."])


def cardio_cha2ds2_vasc(age_years: int, sex: str, heart_failure: bool, hypertension: bool,
                         diabetes: bool, stroke_or_tia: bool, vascular_disease: bool) -> dict:
    _range("Возраст", age_years, 18, 120)
    if sex not in ("male", "female"):
        raise ValueError("sex должен быть 'male' или 'female'.")
    components = {
        "heart_failure": int(heart_failure),
        "hypertension": int(hypertension),
        "age_75_plus": 2 if age_years >= 75 else 0,
        "diabetes": int(diabetes),
        "stroke_or_tia": 2 * int(stroke_or_tia),
        "vascular_disease": int(vascular_disease),
        "age_65_74": 1 if 65 <= age_years <= 74 else 0,
        "female_sex": int(sex == "female"),
    }
    total = sum(components.values())
    return _output(total, "баллов", "CHA₂DS₂-VASc: оценка факторов риска инсульта при ФП", "cardio_cha2ds2_vasc",
                   components, "info",
                   ["Шкала применяется в контексте фибрилляции предсердий; женский пол — модификатор риска.",
                    "Порог решений зависит от действующих рекомендаций, не рассчитывается здесь."])


def critical_qsofa(respiratory_rate: int, systolic: int, altered_mental_status: bool) -> dict:
    _range("ЧДД", respiratory_rate, 4, 80)
    _range("Систолическое давление", systolic, 40, 300)
    components = {
        "respiratory_rate_ge_22": int(respiratory_rate >= 22),
        "systolic_le_100": int(systolic <= 100),
        "altered_mental_status": int(altered_mental_status),
    }
    total = sum(components.values())
    label = ("qSOFA ≥2: повышенный риск неблагоприятного исхода при подозрении на инфекцию"
             if total >= 2 else "qSOFA <2: низкий балл не исключает сепсис")
    return _output(total, "балла из 3", label, "critical_qsofa", components,
                   "high" if total >= 2 else "info",
                   ["qSOFA не является самостоятельным диагностическим тестом на сепсис."])
