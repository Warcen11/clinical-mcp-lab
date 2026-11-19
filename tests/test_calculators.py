import math
import pytest

from clinical_mcp.common import calculators as c


def test_bmi():
    assert c.bmi(80, 180)["value"] == 24.69
    assert c.bmi(80, 180)["risk"] == "low"


def test_gcs():
    assert c.gcs(4, 5, 6)["value"] == 15
    assert c.gcs(1, 1, 1)["value"] == 3


def test_cockcroft_gault():
    assert c.creatinine_clearance(40, 70, 1.0, "male")["value"] == 97.2
    assert c.creatinine_clearance(40, 70, 1.0, "female")["value"] == 82.6


def test_map():
    assert c.cardio_map(120, 80)["value"] == 93.3


def test_cha2ds2_vasc():
    value = c.cardio_cha2ds2_vasc(76, "female", True, True, False, True, True)
    assert value["value"] == 8


def test_qsofa():
    assert c.critical_qsofa(24, 90, False)["value"] == 2
    assert c.critical_qsofa(16, 120, False)["value"] == 0


@pytest.mark.parametrize("fn,args", [
    (c.bmi, (0, 180)),
    (c.gcs, (5, 5, 6)),
    (c.cardio_map, (70, 90)),
    (c.creatinine_clearance, (40, 70, 0, "male")),
    (c.critical_qsofa, (100, 90, False)),
])
def test_rejects_bad_values(fn, args):
    with pytest.raises(ValueError):
        fn(*args)
