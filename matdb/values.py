"""Значение с происхождением.

Центральная идея базы: ни одно число не хранится «голым». У каждого параметра
есть статус достоверности, и код обязан различать «взято из TDS, человек не
смотрел» и «человек подтвердил». Неверно извлечённое из даташита число выглядит
ровно так же убедительно, как верное, — единственная защита в том, чтобы
разница была видна на уровне типа данных, а не в примечании мелким шрифтом.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Status(str, Enum):
    """Откуда взялось значение и насколько ему можно верить."""

    VERIFIED = "verified"
    """Человек сверил с исходным TDS и подтвердил. Можно публиковать как факт."""

    TDS = "tds"
    """Извлечено из TDS автоматически или вручную, но не перепроверено.
    Пригодно для работы, непригодно для публикации без пометки."""

    REFERENCE = "reference"
    """Общее свойство химического семейства из справочной литературы, не
    привязанное к конкретному продукту. Ориентир, а не паспортное значение."""

    ESTIMATED = "estimated"
    """Получено расчётом или эмпирическим правилом внутри этой базы
    (например, пересчёт времени межслойной выдержки на другую температуру)."""

    UNKNOWN = "unknown"
    """Параметр нужен, но его нет. Явная дыра в данных, а не отсутствие поля."""


#: Статусы, которые нельзя показывать пользователю как утверждение о продукте.
UNTRUSTED = frozenset({Status.TDS, Status.REFERENCE, Status.ESTIMATED, Status.UNKNOWN})


class UnverifiedValueError(RuntimeError):
    """Попытка использовать неподтверждённое значение в строгом режиме."""


@dataclass(frozen=True)
class Value:
    """Число (или строка/диапазон) вместе с его происхождением.

    ``value`` = ``None`` допустимо только при статусе ``UNKNOWN``: это способ
    сказать «мы знаем, что не знаем», и такие записи попадают в отчёт о пробелах.
    """

    value: Any
    unit: str | None = None
    status: Status = Status.UNKNOWN
    source: str | None = None
    """Ссылка на источник: ``tds:alchimica/isoflex-pu-500@2023-06#p2`` или URL."""
    note: str | None = None
    verified_by: str | None = None
    verified_at: _dt.date | None = None

    def __post_init__(self) -> None:
        if self.status is Status.UNKNOWN:
            if self.value is not None:
                raise ValueError("статус unknown не может нести значение")
            return
        if self.value is None:
            raise ValueError(f"статус {self.status.value} требует значения")
        if self.status is Status.VERIFIED and not self.verified_by:
            raise ValueError("verified требует указания, кто именно подтвердил")
        if self.status in (Status.TDS, Status.VERIFIED) and not self.source:
            raise ValueError(f"статус {self.status.value} требует ссылки на источник")

    @property
    def known(self) -> bool:
        return self.status is not Status.UNKNOWN

    @property
    def trusted(self) -> bool:
        """Можно ли опираться на это значение при принятии решения на объекте."""
        return self.status is Status.VERIFIED

    def require_trusted(self, what: str) -> Any:
        """Вернуть значение или упасть, если оно не подтверждено человеком."""
        if not self.trusted:
            raise UnverifiedValueError(
                f"{what}: значение имеет статус {self.status.value}, "
                "строгий режим требует verified"
            )
        return self.value

    def render(self) -> str:
        """Человекочитаемая запись с обязательным маркером недостоверности."""
        if not self.known:
            return "нет данных"
        body = f"{self.value}"
        if self.unit:
            body += f" {self.unit}"
        if self.status is Status.VERIFIED:
            return body
        return f"{body} [{self.status.value}]"

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"value": self.value, "status": self.status.value}
        if self.unit:
            out["unit"] = self.unit
        if self.source:
            out["source"] = self.source
        if self.note:
            out["note"] = self.note
        if self.verified_by:
            out["verified_by"] = self.verified_by
        if self.verified_at:
            out["verified_at"] = self.verified_at.isoformat()
        return out

    @classmethod
    def from_json(cls, raw: Any) -> "Value":
        """Разобрать значение из JSON.

        Голое число вместо объекта отвергается: значение без происхождения,
        принятое молча, получает то же доверие, что и проверенное, — ровно тот
        сбой, от которого защищает весь модуль.
        """
        if raw is None:
            return cls(None, status=Status.UNKNOWN)
        if not isinstance(raw, dict):
            raise ValueError(
                f"значение {raw!r} записано без происхождения; ожидается объект "
                'вида {"value": …, "status": …, "source": …}'
            )
        verified_at = raw.get("verified_at")
        return cls(
            value=raw.get("value"),
            unit=raw.get("unit"),
            status=Status(raw.get("status", "unknown")),
            source=raw.get("source"),
            note=raw.get("note"),
            verified_by=raw.get("verified_by"),
            verified_at=_dt.date.fromisoformat(verified_at) if verified_at else None,
        )


def unknown(unit: str | None = None, note: str | None = None) -> Value:
    """Явная дыра в данных — предпочтительнее отсутствующего поля."""
    return Value(None, unit=unit, status=Status.UNKNOWN, note=note)


@dataclass
class Gap:
    """Недостающий параметр — строка рабочей очереди на извлечение из TDS."""

    subject: str
    field_name: str
    unit: str | None = None
    note: str | None = None

    def __str__(self) -> str:
        tail = f" — {self.note}" if self.note else ""
        return f"{self.subject}: {self.field_name}{tail}"


def collect_gaps(subject: str, values: dict[str, Value]) -> list[Gap]:
    """Собрать все ``UNKNOWN`` из набора параметров в очередь на заполнение."""
    return [
        Gap(subject=subject, field_name=name, unit=v.unit, note=v.note)
        for name, v in sorted(values.items())
        if not v.known
    ]


def audit(subject: str, values: dict[str, Value]) -> dict[str, list[str]]:
    """Разложить параметры по статусам — для отчёта о готовности карточки."""
    buckets: dict[str, list[str]] = {s.value: [] for s in Status}
    for name, v in sorted(values.items()):
        buckets[v.status.value].append(name)
    return {k: v for k, v in buckets.items() if v}


__all__ = [
    "Status",
    "UNTRUSTED",
    "UnverifiedValueError",
    "Value",
    "Gap",
    "unknown",
    "collect_gaps",
    "audit",
]
