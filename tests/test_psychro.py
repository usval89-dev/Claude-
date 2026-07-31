"""Проверка психрометрики по независимым опорным точкам."""

from __future__ import annotations

import math

import pytest

from matdb.psychro import (
    PsychroRangeError,
    absolute_humidity,
    dew_point,
    frost_point,
    measure,
    mixing_ratio,
    saturation_pressure,
    surface_rh,
    wet_bulb,
)


def test_saturation_pressure_at_zero():
    # При 0 °C давление насыщения над водой — 6.11 гПа (табличное значение).
    assert saturation_pressure(0.0, over_ice=False) == pytest.approx(6.112, abs=0.01)


@pytest.mark.parametrize(
    "t_c, expected_hpa",
    [
        (10.0, 12.28),
        (20.0, 23.39),
        (30.0, 42.47),
        (40.0, 73.85),
    ],
)
def test_saturation_pressure_table(t_c, expected_hpa):
    # Сверка с таблицами давления насыщенного пара; допуск 1 % — заявленная
    # погрешность аппроксимации Магнуса.
    assert saturation_pressure(t_c, over_ice=False) == pytest.approx(
        expected_hpa, rel=0.01
    )


def test_dew_point_at_full_saturation():
    # При 100 % влажности точка росы равна температуре воздуха.
    for t in (-10.0, 0.0, 15.0, 30.0):
        assert dew_point(t, 100.0) == pytest.approx(t, abs=0.05)


@pytest.mark.parametrize(
    "t_c, rh, expected_td",
    [
        (20.0, 50.0, 9.3),
        (25.0, 60.0, 16.7),
        (30.0, 80.0, 26.2),
        (10.0, 90.0, 8.4),
        (8.0, 75.0, 3.8),
    ],
)
def test_dew_point_reference_points(t_c, rh, expected_td):
    assert dew_point(t_c, rh) == pytest.approx(expected_td, abs=0.2)


def test_frost_point_above_dew_point_below_freezing():
    # Иней выпадает раньше росы: точка инея выше точки росы при минусе.
    for t, rh in ((-5.0, 80.0), (-15.0, 70.0)):
        assert frost_point(t, rh) > dew_point(t, rh)


def test_frost_point_close_to_dew_point_at_zero():
    assert frost_point(0.0, 100.0) == pytest.approx(dew_point(0.0, 100.0), abs=0.05)


def test_dew_point_monotonic_in_humidity():
    values = [dew_point(20.0, rh) for rh in range(10, 101, 10)]
    assert values == sorted(values)


def test_dew_point_roundtrip_through_saturation():
    # Точка росы — температура, при которой текущее парциальное давление
    # становится давлением насыщения.
    t, rh = 22.0, 65.0
    td = dew_point(t, rh)
    e_actual = saturation_pressure(t, over_ice=False) * rh / 100
    assert saturation_pressure(td, over_ice=False) == pytest.approx(e_actual, rel=1e-6)


def test_dew_point_rejects_impossible_humidity():
    with pytest.raises(PsychroRangeError):
        dew_point(20.0, 101.0)
    with pytest.raises(PsychroRangeError):
        dew_point(20.0, -1.0)
    with pytest.raises(PsychroRangeError):
        dew_point(20.0, 0.1)


def test_surface_rh_equals_air_rh_at_same_temperature():
    assert surface_rh(20.0, 55.0, 20.0) == pytest.approx(55.0, abs=0.01)


def test_surface_rh_hits_100_at_dew_point():
    t, rh = 20.0, 60.0
    td = dew_point(t, rh)
    assert surface_rh(t, rh, td) == pytest.approx(100.0, abs=0.1)


def test_cold_surface_condenses():
    # Классический случай: тёплый влажный воздух, холодная плита.
    assert surface_rh(20.0, 70.0, 10.0) > 100.0


def test_absolute_humidity_reference():
    # 20 °C / 50 % ≈ 8.6 г/м³ по справочным таблицам.
    assert absolute_humidity(20.0, 50.0) == pytest.approx(8.65, rel=0.02)


def test_mixing_ratio_reference():
    # 20 °C / 50 % при 1013.25 гПа ≈ 7.3 г/кг.
    assert mixing_ratio(20.0, 50.0) == pytest.approx(7.3, rel=0.03)


def test_wet_bulb_between_dew_point_and_air():
    t, rh = 25.0, 45.0
    assert dew_point(t, rh) < wet_bulb(t, rh) < t


def test_wet_bulb_out_of_range_returns_none_in_measure():
    # Вне области применимости аппроксимации мокрый термометр не выдумывается.
    p = measure(-30.0, 60.0, -30.0)
    assert p.wet_bulb_c is None
    assert math.isfinite(p.dew_point_c)


def test_measure_flags_condensation():
    p = measure(t_air_c=18.0, rh_percent=85.0, t_surface_c=12.0)
    assert p.condensing is True
    assert p.delta_to_dew_point_k < 0


def test_measure_healthy_conditions():
    p = measure(t_air_c=22.0, rh_percent=45.0, t_surface_c=21.0)
    assert p.condensing is False
    assert p.delta_to_dew_point_k > 5
