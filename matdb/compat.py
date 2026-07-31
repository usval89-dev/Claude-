"""Совместимость материалов.

Совместимость несимметрична: полиуретан по битуму и битум по полиуретану — два
разных вопроса с разными ответами. Поэтому правило всегда задаётся парой
«что кладём» → «на что кладём», и обратное направление отдельной записью.

Разрешение идёт по трём уровням, от частного к общему:
1. правило для конкретной пары продуктов;
2. правило для пары «продукт → семейство» или «семейство → продукт»;
3. правило для пары семейств.
Первое найденное побеждает. Если не нашлось ничего — ответ ``UNKNOWN``, и это
честный ответ, а не ``COMPATIBLE`` по умолчанию.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from .models import CoatingSystem, Family, Material
from .values import Status


class Compat(str, Enum):
    COMPATIBLE = "compatible"
    NEEDS_PRIMER = "needs_primer"
    """Стык работает только через промежуточный слой."""
    CONDITIONAL = "conditional"
    """Работает при выполнении условий из ``conditions``."""
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"

    @property
    def blocking(self) -> bool:
        return self in (Compat.INCOMPATIBLE, Compat.UNKNOWN)


_SEVERITY_ORDER = {
    Compat.COMPATIBLE: 0,
    Compat.CONDITIONAL: 1,
    Compat.NEEDS_PRIMER: 2,
    Compat.UNKNOWN: 3,
    Compat.INCOMPATIBLE: 4,
}


@dataclass(frozen=True)
class Rule:
    """Правило стыка ``over`` поверх ``under``.

    ``over`` и ``under`` — либо ``family:<name>``, либо ``product:<id>``.
    """

    over: str
    under: str
    verdict: Compat
    rationale: str
    conditions: tuple[str, ...] = ()
    primer_families: tuple[Family, ...] = ()
    status: Status = Status.REFERENCE
    source: str | None = None

    @property
    def specificity(self) -> int:
        """Насколько правило конкретно: 2 — пара продуктов, 0 — пара семейств."""
        return sum(1 for side in (self.over, self.under) if side.startswith("product:"))

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "Rule":
        return cls(
            over=raw["over"],
            under=raw["under"],
            verdict=Compat(raw["verdict"]),
            rationale=raw["rationale"],
            conditions=tuple(raw.get("conditions", ())),
            primer_families=tuple(Family(f) for f in raw.get("primer_families", ())),
            status=Status(raw.get("status", "reference")),
            source=raw.get("source"),
        )


@dataclass(frozen=True)
class Resolution:
    """Ответ на вопрос «можно ли класть A на B»."""

    over: str
    under: str
    verdict: Compat
    rationale: str
    conditions: tuple[str, ...] = ()
    primer_families: tuple[Family, ...] = ()
    status: Status = Status.UNKNOWN
    source: str | None = None
    matched_rule: str | None = None

    def render(self) -> str:
        label = {
            Compat.COMPATIBLE: "совместимо",
            Compat.NEEDS_PRIMER: "только через промежуточный слой",
            Compat.CONDITIONAL: "условно совместимо",
            Compat.INCOMPATIBLE: "несовместимо",
            Compat.UNKNOWN: "нет правила",
        }[self.verdict]
        lines = [f"{self.over} по {self.under}: {label}", f"  {self.rationale}"]
        for c in self.conditions:
            lines.append(f"  — {c}")
        if self.primer_families:
            fams = ", ".join(f.value for f in self.primer_families)
            lines.append(f"  промежуточный слой: {fams}")
        if self.status is not Status.VERIFIED:
            lines.append(f"  основание вывода: {self.status.value}")
        return "\n".join(lines)


def _keys_for(material: Material | None, family: Family | None) -> list[str]:
    """Ключи поиска от частного к общему."""
    keys: list[str] = []
    if material is not None:
        keys.append(f"product:{material.id}")
        keys.append(f"family:{material.family.value}")
    elif family is not None:
        keys.append(f"family:{family.value}")
    return keys


@dataclass
class CompatibilityIndex:
    """Индекс правил с разрешением по специфичности."""

    rules: list[Rule] = field(default_factory=list)

    def add(self, rule: Rule) -> None:
        self.rules.append(rule)

    def extend(self, rules: Iterable[Rule]) -> None:
        self.rules.extend(rules)

    def resolve(
        self,
        over: Material | Family,
        under: Material | Family,
    ) -> Resolution:
        over_mat = over if isinstance(over, Material) else None
        under_mat = under if isinstance(under, Material) else None
        over_keys = _keys_for(over_mat, None if over_mat else over)  # type: ignore[arg-type]
        under_keys = _keys_for(under_mat, None if under_mat else under)  # type: ignore[arg-type]

        best: Rule | None = None
        for rule in self.rules:
            if rule.over in over_keys and rule.under in under_keys:
                if best is None or rule.specificity > best.specificity:
                    best = rule

        over_label = over_mat.id if over_mat else over.value  # type: ignore[union-attr]
        under_label = under_mat.id if under_mat else under.value  # type: ignore[union-attr]

        if best is None:
            return Resolution(
                over=over_label,
                under=under_label,
                verdict=Compat.UNKNOWN,
                rationale=(
                    "правила для этой пары нет в базе; отсутствие правила не означает "
                    "совместимость — стык нужно проверить выкраской на адгезию"
                ),
            )
        return Resolution(
            over=over_label,
            under=under_label,
            verdict=best.verdict,
            rationale=best.rationale,
            conditions=best.conditions,
            primer_families=best.primer_families,
            status=best.status,
            source=best.source,
            matched_rule=f"{best.over} → {best.under}",
        )

    def check_system(self, system: CoatingSystem) -> list[Resolution]:
        """Проверить все стыки системы снизу вверх."""
        return [
            self.resolve(upper.material, lower.material)
            for lower, upper in system.pairs()
        ]

    @staticmethod
    def worst(resolutions: Iterable[Resolution]) -> Compat:
        items = list(resolutions)
        if not items:
            return Compat.COMPATIBLE
        return max((r.verdict for r in items), key=lambda v: _SEVERITY_ORDER[v])
