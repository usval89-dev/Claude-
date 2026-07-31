"""Проверка условий нанесения и пересчёт времён на фактическую температуру."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import CureMode, Material
from .psychro import Psychrometrics, measure
from .values import Status, Value

#: Запас над точкой росы по умолчанию, если TDS молчит.
#: ISO 8502-4 и практика лакокрасочных работ: не менее 3 K.
DEFAULT_DEW_POINT_MARGIN_K = 3.0

#: Во сколько раз меняется скорость реакции на каждые 10 °C.
#: Приближение Аррениуса; для полиуретанов и эпоксидов в диапазоне +5…+35 °C
#: даёт правильный порядок величины, но не заменяет данные производителя.
Q10 = 2.0

#: Границы, за которыми пересчёт по Q10 перестаёт быть осмысленным.
Q10_VALID_RANGE_C = (0.0, 40.0)

#: Влажность, с которой влагоотверждаемые составы начинают пузыриться в толще.
#: Порог намеренно ниже типового паспортного предела (85 %): предупреждение
#: должно закрывать полосу, где формально всё в допуске, а плёнка уже в риске.
MOISTURE_FOAMING_RH = 80.0

#: Влажность, ниже которой влагоотверждаемый состав заметно теряет скорость.
MOISTURE_SLOW_CURE_RH = 35.0


class Severity(str, Enum):
    OK = "ok"
    WARN = "warn"
    """Работать можно, но результат зависит от факторов вне расчёта."""
    STOP = "stop"
    """Нарушено паспортное ограничение — наносить нельзя."""
    NO_DATA = "no_data"
    """Проверка не выполнена: параметра нет в карточке."""


@dataclass(frozen=True)
class Check:
    name: str
    severity: Severity
    message: str
    basis: Status | None = None
    """Статус данных, на которых построена проверка."""

    def __str__(self) -> str:
        mark = {
            Severity.OK: "OK  ",
            Severity.WARN: "ВНИМ",
            Severity.STOP: "СТОП",
            Severity.NO_DATA: "?   ",
        }[self.severity]
        tail = ""
        if self.basis and self.basis is not Status.VERIFIED:
            tail = f" (данные: {self.basis.value})"
        return f"[{mark}] {self.name}: {self.message}{tail}"


@dataclass
class Verdict:
    material_id: str
    psychro: Psychrometrics
    checks: list[Check]

    @property
    def severity(self) -> Severity:
        for level in (Severity.STOP, Severity.WARN, Severity.NO_DATA, Severity.OK):
            if any(c.severity is level for c in self.checks):
                return level
        return Severity.OK

    @property
    def can_apply(self) -> bool:
        return self.severity is Severity.OK

    def report(self) -> str:
        p = self.psychro
        head = [
            f"Материал: {self.material_id}",
            f"Воздух {p.t_air_c:.1f} °C / {p.rh_percent:.0f} %, "
            f"основание {p.t_surface_c:.1f} °C",
            f"Точка росы {p.dew_point_c:.1f} °C, запас {p.delta_to_dew_point_k:+.1f} K, "
            f"влажность у поверхности {p.surface_rh_percent:.0f} %",
        ]
        return "\n".join(head + [str(c) for c in self.checks])


def _range_check(
    name: str,
    actual: float,
    lo: Value,
    hi: Value,
    unit: str,
    *,
    what: str,
) -> Check:
    """Общая проверка «попадает ли замер в паспортный диапазон»."""
    if not lo.known and not hi.known:
        return Check(name, Severity.NO_DATA, f"{what} не указан в карточке")
    basis = min(
        (v.status for v in (lo, hi) if v.known),
        key=lambda s: 0 if s is Status.VERIFIED else 1,
    )
    if lo.known and actual < float(lo.value):
        return Check(
            name,
            Severity.STOP,
            f"{actual:.1f} {unit} ниже минимума {lo.value} {unit}",
            basis,
        )
    if hi.known and actual > float(hi.value):
        return Check(
            name,
            Severity.STOP,
            f"{actual:.1f} {unit} выше максимума {hi.value} {unit}",
            basis,
        )
    bounds = "…".join(
        str(v.value) if v.known else "—" for v in (lo, hi)
    )
    return Check(name, Severity.OK, f"{actual:.1f} {unit} в пределах {bounds} {unit}", basis)


def check_application(
    material: Material,
    *,
    t_air_c: float,
    rh_percent: float,
    t_surface_c: float,
    substrate_moisture_percent: float | None = None,
    expected_temp_drop_k: float = 0.0,
) -> Verdict:
    """Полная проверка «можно ли наносить прямо сейчас».

    ``expected_temp_drop_k`` — ожидаемое падение температуры основания за время
    до отлипа. Утренняя заливка часто проходит по всем пределам, а к вечеру
    плита уходит под точку росы, пока плёнка ещё открыта.
    """
    p = measure(t_air_c, rh_percent, t_surface_c)
    limits = material.application
    checks: list[Check] = []

    # 1. Точка росы — главная проверка, поэтому первая.
    margin_v = limits.dew_point_margin_k
    if margin_v.known:
        required = float(margin_v.value)
        basis = margin_v.status
    else:
        required = DEFAULT_DEW_POINT_MARGIN_K
        basis = Status.REFERENCE
    actual = p.delta_to_dew_point_k
    if actual <= 0:
        checks.append(
            Check(
                "Точка росы",
                Severity.STOP,
                f"основание на {-actual:.1f} K ниже точки росы — идёт конденсация",
                basis,
            )
        )
    elif actual < required:
        checks.append(
            Check(
                "Точка росы",
                Severity.STOP,
                f"запас {actual:.1f} K меньше требуемых {required:.0f} K",
                basis,
            )
        )
    else:
        checks.append(
            Check(
                "Точка росы",
                Severity.OK,
                f"запас {actual:.1f} K при требуемых {required:.0f} K",
                basis,
            )
        )

    # 2. Прогноз: остынет ли основание ниже порога, пока плёнка открыта.
    if expected_temp_drop_k > 0:
        future = actual - expected_temp_drop_k
        if future <= 0:
            sev, msg = Severity.STOP, (
                f"при остывании на {expected_temp_drop_k:.1f} K основание уйдёт "
                f"под точку росы ({future:+.1f} K) до отлипа"
            )
        elif future < required:
            sev, msg = Severity.WARN, (
                f"при остывании на {expected_temp_drop_k:.1f} K запас упадёт до "
                f"{future:.1f} K — меньше требуемых {required:.0f} K"
            )
        else:
            sev, msg = Severity.OK, (
                f"с учётом остывания на {expected_temp_drop_k:.1f} K запас "
                f"останется {future:.1f} K"
            )
        checks.append(Check("Прогноз до отлипа", sev, msg, basis))

    # 3. Температура основания и воздуха.
    checks.append(
        _range_check(
            "Температура основания",
            t_surface_c,
            limits.substrate_temp_min_c,
            limits.substrate_temp_max_c,
            "°C",
            what="диапазон температуры основания",
        )
    )
    checks.append(
        _range_check(
            "Температура воздуха",
            t_air_c,
            limits.ambient_temp_min_c,
            limits.ambient_temp_max_c,
            "°C",
            what="диапазон температуры воздуха",
        )
    )

    # 4. Влажность воздуха. Для влагоотверждаемых систем опасны обе границы.
    checks.append(
        _range_check(
            "Влажность воздуха",
            rh_percent,
            limits.ambient_rh_min_percent,
            limits.ambient_rh_max_percent,
            "%",
            what="диапазон влажности воздуха",
        )
    )
    if material.cure_mode is CureMode.MOISTURE and rh_percent >= MOISTURE_FOAMING_RH:
        checks.append(
            Check(
                "Вспенивание",
                Severity.WARN,
                f"влагоотверждаемый состав при RH {rh_percent:.0f} % и толстом слое "
                "склонен к выделению CO₂ и пузырению",
                Status.REFERENCE,
            )
        )
    if material.cure_mode is CureMode.MOISTURE and rh_percent < MOISTURE_SLOW_CURE_RH:
        checks.append(
            Check(
                "Скорость отверждения",
                Severity.WARN,
                f"при RH {rh_percent:.0f} % влагоотверждаемый состав набирает "
                "прочность заметно медленнее паспортных значений",
                Status.REFERENCE,
            )
        )

    # 5. Влажность основания.
    moisture_limit = limits.substrate_moisture_max_percent
    if substrate_moisture_percent is None:
        checks.append(
            Check("Влажность основания", Severity.NO_DATA, "замер не передан")
        )
    elif not moisture_limit.known:
        checks.append(
            Check(
                "Влажность основания",
                Severity.NO_DATA,
                f"замер {substrate_moisture_percent:.1f} %, предел в карточке не указан",
            )
        )
    elif substrate_moisture_percent > float(moisture_limit.value):
        checks.append(
            Check(
                "Влажность основания",
                Severity.STOP,
                f"{substrate_moisture_percent:.1f} % выше предела "
                f"{moisture_limit.value} % ({moisture_limit.note or 'метод не указан'})",
                moisture_limit.status,
            )
        )
    else:
        checks.append(
            Check(
                "Влажность основания",
                Severity.OK,
                f"{substrate_moisture_percent:.1f} % при пределе {moisture_limit.value} %",
                moisture_limit.status,
            )
        )

    # 6. Конденсация на поверхности как отдельный сигнал.
    if p.surface_rh_percent >= 100:
        checks.append(
            Check(
                "Состояние поверхности",
                Severity.STOP,
                f"расчётная влажность у поверхности {p.surface_rh_percent:.0f} % — "
                "плита мокрая, даже если визуально сухая",
                Status.REFERENCE,
            )
        )

    return Verdict(material_id=material.id, psychro=p, checks=checks)


@dataclass(frozen=True)
class TimeEstimate:
    """Пересчитанное время с явным указанием, что это оценка."""

    name: str
    hours: float | None
    status: Status
    basis: str

    def render(self) -> str:
        if self.hours is None:
            return f"{self.name}: нет данных"
        if self.hours >= 48:
            body = f"{self.hours / 24:.1f} сут"
        else:
            body = f"{self.hours:.1f} ч"
        mark = "" if self.status is Status.VERIFIED else f" [{self.status.value}]"
        return f"{self.name}: {body}{mark} — {self.basis}"


def adjust_time(value: Value, reference_temp_c: Value, actual_temp_c: float) -> TimeEstimate:
    """Пересчитать паспортное время на фактическую температуру по правилу Q10.

    Результат всегда получает статус ``ESTIMATED``, даже если исходное значение
    подтверждено: пересчёт — это наша модель, а не данные производителя.
    """
    name = "время"
    if not value.known:
        return TimeEstimate(name, None, Status.UNKNOWN, "нет паспортного значения")
    hours = float(value.value)
    if not reference_temp_c.known:
        return TimeEstimate(
            name,
            hours,
            value.status,
            "опорная температура не указана, пересчёт невозможен",
        )
    t_ref = float(reference_temp_c.value)
    if abs(actual_temp_c - t_ref) < 0.5:
        return TimeEstimate(name, hours, value.status, f"паспортное значение при {t_ref:.0f} °C")
    lo, hi = Q10_VALID_RANGE_C
    if not lo <= actual_temp_c <= hi:
        return TimeEstimate(
            name,
            None,
            Status.UNKNOWN,
            f"{actual_temp_c:.0f} °C вне диапазона, где правило Q10 осмысленно "
            f"({lo:.0f}…{hi:.0f} °C) — нужны данные производителя",
        )
    factor = Q10 ** ((t_ref - actual_temp_c) / 10.0)
    return TimeEstimate(
        name,
        hours * factor,
        Status.ESTIMATED,
        f"оценка по правилу Q10={Q10:g} от {hours:g} ч при {t_ref:.0f} °C "
        f"(коэффициент ×{factor:.2f})",
    )


def cure_schedule(material: Material, t_surface_c: float) -> list[TimeEstimate]:
    """Пересчитать весь график отверждения на фактическую температуру."""
    ref = material.cure.reference_temp_c
    out: list[TimeEstimate] = []
    for label, value in (
        ("Отлип", material.cure.tack_free_h),
        ("Межслойное окно, минимум", material.cure.overcoat_min_h),
        ("Межслойное окно, максимум", material.cure.overcoat_max_h),
        ("Пешая нагрузка", material.cure.foot_traffic_h),
    ):
        est = adjust_time(value, ref, t_surface_c)
        out.append(
            TimeEstimate(label, est.hours, est.status, est.basis)
        )
    return out
