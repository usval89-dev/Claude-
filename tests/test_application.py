"""Проверка решающего правила «можно ли наносить»."""

from __future__ import annotations

import pytest

from matdb.application import Q10, Severity, adjust_time, check_application, cure_schedule
from matdb.values import Status, Value


def find(verdict, name):
    for c in verdict.checks:
        if c.name == name:
            return c
    raise AssertionError(f"проверка {name!r} не выполнялась")


def test_good_conditions_pass(pu_membrane):
    v = check_application(
        pu_membrane, t_air_c=22.0, rh_percent=50.0, t_surface_c=21.0,
        substrate_moisture_percent=2.5,
    )
    assert v.can_apply
    assert v.severity is Severity.OK


def test_condensation_stops_work(pu_membrane):
    v = check_application(
        pu_membrane, t_air_c=18.0, rh_percent=90.0, t_surface_c=12.0,
        substrate_moisture_percent=2.0,
    )
    assert not v.can_apply
    check = find(v, "Точка росы")
    assert check.severity is Severity.STOP
    assert "конденсация" in check.message


def test_margin_below_requirement_stops_work(pu_membrane):
    # Основание выше точки росы, но запас меньше паспортных 3 K.
    v = check_application(
        pu_membrane, t_air_c=15.0, rh_percent=80.0, t_surface_c=12.5,
        substrate_moisture_percent=2.0,
    )
    check = find(v, "Точка росы")
    assert check.severity is Severity.STOP
    assert 0 < v.psychro.delta_to_dew_point_k < 3


def test_forecast_catches_evening_drop(pu_membrane):
    # Утром всё в допуске, но плита остынет на 6 K, пока плёнка открыта.
    v = check_application(
        pu_membrane, t_air_c=16.0, rh_percent=70.0, t_surface_c=17.0,
        substrate_moisture_percent=2.0, expected_temp_drop_k=6.0,
    )
    assert find(v, "Точка росы").severity is Severity.OK
    assert find(v, "Прогноз до отлипа").severity in (Severity.WARN, Severity.STOP)
    assert not v.can_apply


def test_no_forecast_check_without_expected_drop(pu_membrane):
    v = check_application(
        pu_membrane, t_air_c=22.0, rh_percent=50.0, t_surface_c=21.0,
        substrate_moisture_percent=2.0,
    )
    with pytest.raises(AssertionError):
        find(v, "Прогноз до отлипа")


def test_cold_substrate_stops_work(pu_membrane):
    v = check_application(
        pu_membrane, t_air_c=6.0, rh_percent=40.0, t_surface_c=2.0,
        substrate_moisture_percent=2.0,
    )
    assert find(v, "Температура основания").severity is Severity.STOP


def test_wet_substrate_stops_work(pu_membrane):
    v = check_application(
        pu_membrane, t_air_c=22.0, rh_percent=50.0, t_surface_c=21.0,
        substrate_moisture_percent=6.0,
    )
    check = find(v, "Влажность основания")
    assert check.severity is Severity.STOP
    assert "весовой метод" in check.message


def test_missing_moisture_reading_is_not_a_pass(pu_membrane):
    v = check_application(
        pu_membrane, t_air_c=22.0, rh_percent=50.0, t_surface_c=21.0
    )
    assert find(v, "Влажность основания").severity is Severity.NO_DATA
    assert not v.can_apply, "отсутствие замера не должно засчитываться как проход"


def test_empty_card_yields_no_data_not_approval(empty_card):
    v = check_application(
        empty_card, t_air_c=22.0, rh_percent=50.0, t_surface_c=21.0,
        substrate_moisture_percent=2.0,
    )
    assert not v.can_apply
    assert v.severity is Severity.NO_DATA
    # Без паспортного запаса подставляется справочные 3 K, а не «всё хорошо».
    assert find(v, "Точка росы").basis is Status.REFERENCE


def test_high_humidity_warns_about_foaming(pu_membrane):
    v = check_application(
        pu_membrane, t_air_c=24.0, rh_percent=84.0, t_surface_c=23.0,
        substrate_moisture_percent=2.0,
    )
    assert find(v, "Вспенивание").severity is Severity.WARN


def test_dry_air_warns_about_slow_cure(pu_membrane):
    v = check_application(
        pu_membrane, t_air_c=24.0, rh_percent=25.0, t_surface_c=23.0,
        substrate_moisture_percent=2.0,
    )
    assert find(v, "Скорость отверждения").severity is Severity.WARN


def test_report_is_human_readable(pu_membrane):
    v = check_application(
        pu_membrane, t_air_c=22.0, rh_percent=50.0, t_surface_c=21.0,
        substrate_moisture_percent=2.0,
    )
    text = v.report()
    assert "Точка росы" in text
    assert "fixture-pu" in text


# --- пересчёт времён -------------------------------------------------------


def test_cold_doubles_time_per_ten_degrees():
    value = Value(6, unit="ч", status=Status.TDS, source="s")
    ref = Value(20, unit="°C", status=Status.TDS, source="s")
    est = adjust_time(value, ref, 10.0)
    assert est.hours == pytest.approx(6 * Q10)
    assert est.status is Status.ESTIMATED


def test_warmth_halves_time_per_ten_degrees():
    value = Value(6, unit="ч", status=Status.TDS, source="s")
    ref = Value(20, unit="°C", status=Status.TDS, source="s")
    assert adjust_time(value, ref, 30.0).hours == pytest.approx(3.0)


def test_no_adjustment_keeps_original_status():
    value = Value(6, unit="ч", status=Status.VERIFIED, source="s", verified_by="я")
    ref = Value(20, unit="°C", status=Status.VERIFIED, source="s", verified_by="я")
    est = adjust_time(value, ref, 20.0)
    assert est.status is Status.VERIFIED
    assert est.hours == 6


def test_adjustment_downgrades_verified_to_estimated():
    # Пересчёт — наша модель, а не данные производителя, даже если исходник
    # подтверждён человеком.
    value = Value(6, unit="ч", status=Status.VERIFIED, source="s", verified_by="я")
    ref = Value(20, unit="°C", status=Status.VERIFIED, source="s", verified_by="я")
    assert adjust_time(value, ref, 12.0).status is Status.ESTIMATED


def test_extreme_cold_refuses_to_extrapolate():
    value = Value(6, unit="ч", status=Status.TDS, source="s")
    ref = Value(20, unit="°C", status=Status.TDS, source="s")
    est = adjust_time(value, ref, -8.0)
    assert est.hours is None
    assert "Q10" in est.basis


def test_missing_reference_temperature_blocks_recalculation():
    from matdb.values import unknown

    est = adjust_time(Value(6, unit="ч", status=Status.TDS, source="s"), unknown("°C"), 10.0)
    assert est.hours == 6
    assert "опорная температура не указана" in est.basis


def test_schedule_covers_all_stages(pu_membrane):
    stages = cure_schedule(pu_membrane, 10.0)
    names = [s.name for s in stages]
    assert "Межслойное окно, минимум" in names
    assert "Межслойное окно, максимум" in names
    # На холоде окно расширяется в обе стороны.
    by_name = {s.name: s for s in stages}
    assert by_name["Межслойное окно, минимум"].hours > 8
    assert by_name["Межслойное окно, максимум"].hours > 48


def test_schedule_of_empty_card_reports_no_data(empty_card):
    for est in cure_schedule(empty_card, 15.0):
        assert est.hours is None
        assert "нет данных" in est.render()
