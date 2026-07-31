"""Фикстуры.

Все числовые значения здесь вымышлены и существуют только ради проверки логики.
Они намеренно не попадают в ``data/``: выдуманный параметр в базе неотличим от
извлечённого из TDS, и однажды кто-нибудь на него сошлётся.
"""

from __future__ import annotations

import pytest

from matdb.models import (
    ApplicationLimits,
    Consumption,
    CureMode,
    CureProfile,
    Family,
    Material,
    Role,
    TdsRef,
)
from matdb.values import Status, Value


def v(value, unit, status=Status.TDS, **kw):
    if status in (Status.TDS, Status.VERIFIED):
        kw.setdefault("source", "tds:fixture@0000-00#p0")
    if status is Status.VERIFIED:
        kw.setdefault("verified_by", "фикстура")
    return Value(value, unit=unit, status=status, **kw)


@pytest.fixture
def pu_membrane() -> Material:
    """Полностью заполненная карточка — вымышленный продукт."""
    return Material(
        id="fixture-pu",
        name="Fixture PU (вымышленный продукт)",
        manufacturer="Fixture Chemicals",
        family=Family.PU_1K_MOISTURE,
        roles=(Role.MEMBRANE,),
        cure_mode=CureMode.MOISTURE,
        tds=TdsRef(url="https://example.invalid/tds", revision="0"),
        application=ApplicationLimits(
            substrate_temp_min_c=v(5, "°C", Status.VERIFIED),
            substrate_temp_max_c=v(35, "°C", Status.VERIFIED),
            ambient_temp_min_c=v(5, "°C"),
            ambient_temp_max_c=v(35, "°C"),
            ambient_rh_max_percent=v(85, "%", Status.VERIFIED),
            dew_point_margin_k=v(3, "K", Status.VERIFIED),
            substrate_moisture_max_percent=v(
                4, "%", Status.VERIFIED, note="весовой метод"
            ),
        ),
        cure=CureProfile(
            reference_temp_c=v(20, "°C", Status.VERIFIED),
            tack_free_h=v(6, "ч"),
            overcoat_min_h=v(8, "ч"),
            overcoat_max_h=v(48, "ч"),
            foot_traffic_h=v(24, "ч"),
        ),
        consumption=Consumption(per_coat_kg_m2=v(0.7, "кг/м²"), coats=v(2, "шт")),
    )


@pytest.fixture
def empty_card() -> Material:
    """Свежая карточка без единого параметра — нормальное стартовое состояние."""
    return Material(
        id="fixture-empty",
        name="Fixture Empty",
        manufacturer="Fixture Chemicals",
        family=Family.EPOXY_2K,
        roles=(Role.PRIMER,),
        cure_mode=CureMode.CHEMICAL,
    )
