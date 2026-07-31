"""Психрометрика: точка росы, влагосодержание, относительная влажность у поверхности.

Все формулы — общепринятые инженерные аппроксимации с указанными границами
применимости. Источники указаны в докстрингах функций; это единственный модуль
в проекте, где числа берутся не из TDS, а из физики, и потому не требуют
подтверждения человеком.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Коэффициенты Магнуса в редакции Sonntag (1990), над водой.
# Погрешность es < 0.4 % в диапазоне -45…+60 °C.
MAGNUS_A_WATER = 6.112  # гПа
MAGNUS_B_WATER = 17.62
MAGNUS_C_WATER = 243.12  # °C
WATER_RANGE = (-45.0, 60.0)

# Над льдом (Sonntag 1990), -65…0 °C.
MAGNUS_A_ICE = 6.112
MAGNUS_B_ICE = 22.46
MAGNUS_C_ICE = 272.62
ICE_RANGE = (-65.0, 0.0)

STANDARD_PRESSURE_HPA = 1013.25

# Газовая постоянная водяного пара, Дж/(кг·К) — для абсолютной влажности.
R_VAPOUR = 461.5


class PsychroRangeError(ValueError):
    """Аргумент вне диапазона применимости формулы."""


def _check_rh(rh: float) -> None:
    if not 0.0 <= rh <= 100.0:
        raise PsychroRangeError(f"относительная влажность {rh} вне диапазона 0…100 %")


def saturation_pressure(t_c: float, *, over_ice: bool | None = None) -> float:
    """Давление насыщенного водяного пара, гПа.

    Формула Магнуса (Sonntag 1990). При ``over_ice=None`` выбор поверхности
    автоматический: ниже 0 °C считаем надо льдом.
    """
    if over_ice is None:
        over_ice = t_c < 0.0
    if over_ice:
        lo, hi = ICE_RANGE
        a, b, c = MAGNUS_A_ICE, MAGNUS_B_ICE, MAGNUS_C_ICE
    else:
        lo, hi = WATER_RANGE
        a, b, c = MAGNUS_A_WATER, MAGNUS_B_WATER, MAGNUS_C_WATER
    if not lo <= t_c <= hi:
        raise PsychroRangeError(
            f"температура {t_c} °C вне диапазона применимости формулы {lo}…{hi} °C"
        )
    return a * math.exp(b * t_c / (c + t_c))


def vapour_pressure(t_air_c: float, rh_percent: float) -> float:
    """Парциальное давление водяного пара в воздухе, гПа.

    Относительная влажность по метеорологическому соглашению (и по показаниям
    любого объектного гигрометра) отсчитывается от насыщения над водой, в том
    числе при отрицательных температурах. Поэтому здесь всегда ``over_ice=False``:
    смешение двух шкал даёт расхождение точки росы почти в полтора градуса при
    -10 °C.
    """
    _check_rh(rh_percent)
    return saturation_pressure(t_air_c, over_ice=False) * rh_percent / 100.0


def dew_point(t_air_c: float, rh_percent: float) -> float:
    """Точка росы, °C.

    Обратное преобразование формулы Магнуса над водой. Для RH → 0 результат
    уходит в минус бесконечность, поэтому влажность ниже 0.5 % отсекается:
    на практике таких условий на объекте не бывает, а численно формула теряет
    смысл.
    """
    _check_rh(rh_percent)
    if rh_percent < 0.5:
        raise PsychroRangeError(
            "точка росы не считается при относительной влажности ниже 0.5 %"
        )
    e = vapour_pressure(t_air_c, rh_percent)
    gamma = math.log(e / MAGNUS_A_WATER)
    return MAGNUS_C_WATER * gamma / (MAGNUS_B_WATER - gamma)


def frost_point(t_air_c: float, rh_percent: float) -> float:
    """Точка инея, °C — температура выпадения кристаллов, а не капель.

    Отличается от точки росы: ниже 0 °C поверхность покрывается инеем при
    температуре на несколько десятых градуса выше расчётной точки росы. Для
    приёмки покрытий значима именно точка росы, но при работе по холодному
    металлу разница объясняет, почему плита «седеет» раньше расчёта.
    """
    _check_rh(rh_percent)
    if rh_percent < 0.5:
        raise PsychroRangeError(
            "точка инея не считается при относительной влажности ниже 0.5 %"
        )
    e = vapour_pressure(t_air_c, rh_percent)
    gamma = math.log(e / MAGNUS_A_ICE)
    return MAGNUS_C_ICE * gamma / (MAGNUS_B_ICE - gamma)


def surface_rh(t_air_c: float, rh_percent: float, t_surface_c: float) -> float:
    """Относительная влажность в тонком слое воздуха у поверхности, %.

    Считаем, что влагосодержание воздуха у поверхности то же, что в объёме,
    а температура — поверхности. Значение ≥ 100 % означает конденсацию.
    Именно эта величина, а не влажность воздуха, определяет, «потеет» ли плита.
    """
    e = vapour_pressure(t_air_c, rh_percent)
    es_surface = saturation_pressure(t_surface_c, over_ice=False)
    return 100.0 * e / es_surface


def absolute_humidity(t_air_c: float, rh_percent: float) -> float:
    """Абсолютная влажность, г/м³ (масса пара в кубометре воздуха)."""
    e_pa = vapour_pressure(t_air_c, rh_percent) * 100.0
    t_k = t_air_c + 273.15
    return 1000.0 * e_pa / (R_VAPOUR * t_k)


def mixing_ratio(
    t_air_c: float, rh_percent: float, pressure_hpa: float = STANDARD_PRESSURE_HPA
) -> float:
    """Влагосодержание, г пара на кг сухого воздуха."""
    e = vapour_pressure(t_air_c, rh_percent)
    if e >= pressure_hpa:
        raise PsychroRangeError("парциальное давление пара не может превышать полное")
    return 1000.0 * 0.621945 * e / (pressure_hpa - e)


def wet_bulb(t_air_c: float, rh_percent: float) -> float:
    """Температура мокрого термометра, °C — аппроксимация Stull (2011).

    Заявленная точность ±0.65 °C при RH 5…99 % и T -20…+50 °C, при нормальном
    давлении. Используется как ориентир скорости испарения, не как расчётная
    величина для приёмки.
    """
    _check_rh(rh_percent)
    if not 5.0 <= rh_percent <= 99.0 or not -20.0 <= t_air_c <= 50.0:
        raise PsychroRangeError(
            "аппроксимация Stull применима при RH 5…99 % и T -20…+50 °C"
        )
    t, rh = t_air_c, rh_percent
    return (
        t * math.atan(0.151977 * math.sqrt(rh + 8.313659))
        + math.atan(t + rh)
        - math.atan(rh - 1.676331)
        + 0.00391838 * rh**1.5 * math.atan(0.023101 * rh)
        - 4.686035
    )


@dataclass(frozen=True)
class Psychrometrics:
    """Полный психрометрический срез для одного замера на объекте."""

    t_air_c: float
    rh_percent: float
    t_surface_c: float
    dew_point_c: float
    surface_rh_percent: float
    delta_to_dew_point_k: float
    absolute_humidity_g_m3: float
    mixing_ratio_g_kg: float
    vapour_pressure_hpa: float
    wet_bulb_c: float | None

    @property
    def condensing(self) -> bool:
        """Поверхность холоднее точки росы — конденсат уже идёт."""
        return self.delta_to_dew_point_k <= 0.0


def measure(t_air_c: float, rh_percent: float, t_surface_c: float) -> Psychrometrics:
    """Свести один замер (воздух + поверхность) в набор производных величин."""
    td = dew_point(t_air_c, rh_percent)
    try:
        twb: float | None = wet_bulb(t_air_c, rh_percent)
    except PsychroRangeError:
        twb = None
    return Psychrometrics(
        t_air_c=t_air_c,
        rh_percent=rh_percent,
        t_surface_c=t_surface_c,
        dew_point_c=td,
        surface_rh_percent=surface_rh(t_air_c, rh_percent, t_surface_c),
        delta_to_dew_point_k=t_surface_c - td,
        absolute_humidity_g_m3=absolute_humidity(t_air_c, rh_percent),
        mixing_ratio_g_kg=mixing_ratio(t_air_c, rh_percent),
        vapour_pressure_hpa=vapour_pressure(t_air_c, rh_percent),
        wet_bulb_c=twb,
    )
