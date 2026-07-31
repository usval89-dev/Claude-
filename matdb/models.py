"""Модель предметной области: материал, слой, система покрытия."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from .values import Gap, Status, Value, collect_gaps, unknown


class Family(str, Enum):
    """Химическое семейство. Определяет базовую совместимость и режим отверждения."""

    PU_1K_MOISTURE = "pu_1k_moisture"
    """Однокомпонентный полиуретан влажностного отверждения."""
    PU_2K = "pu_2k"
    PU_CEMENT = "pu_cement"
    EPOXY_2K = "epoxy_2k"
    EPOXY_WB = "epoxy_wb"
    """Эпоксид на водной основе / водно-дисперсионный."""
    PMMA = "pmma"
    POLYUREA = "polyurea"
    ACRYLIC_WB = "acrylic_wb"
    BITUMEN = "bitumen"
    BITUMEN_POLYMER = "bitumen_polymer"
    CEMENTITIOUS = "cementitious"
    CEMENTITIOUS_POLYMER = "cementitious_polymer"
    SILICATE = "silicate"
    SILANE_SILOXANE = "silane_siloxane"
    MS_POLYMER = "ms_polymer"
    SILICONE = "silicone"
    UNKNOWN = "unknown"


class Role(str, Enum):
    """Функция материала в системе — определяет, что с чем стыкуется."""

    SUBSTRATE = "substrate"
    PRIMER = "primer"
    MEMBRANE = "membrane"
    INTERMEDIATE = "intermediate"
    TOPCOAT = "topcoat"
    SEALANT = "sealant"
    REPAIR_MORTAR = "repair_mortar"
    SCREED = "screed"


class CureMode(str, Enum):
    """Механизм набора прочности — от него зависит роль влажности и температуры."""

    MOISTURE = "moisture"
    """Отверждение влагой воздуха: низкая влажность тормозит, высокая — вспенивает."""
    CHEMICAL = "chemical"
    """Реакция двух компонентов: влага мешает, температура ускоряет."""
    EVAPORATION = "evaporation"
    """Испарение воды или растворителя: высокая влажность тормозит напрямую."""
    HYDRATION = "hydration"
    """Гидратация цемента: требует влаги, боится пересыхания."""
    RADIATION = "radiation"


#: Параметры карточки материала, без которых нельзя ответить «можно ли класть».
REQUIRED_APPLICATION_FIELDS = (
    "substrate_temp_min_c",
    "substrate_temp_max_c",
    "dew_point_margin_k",
    "substrate_moisture_max_percent",
    "ambient_rh_max_percent",
)


@dataclass
class ApplicationLimits:
    """Условия нанесения. Каждое поле — ``Value`` со своим происхождением."""

    substrate_temp_min_c: Value = field(default_factory=lambda: unknown("°C"))
    substrate_temp_max_c: Value = field(default_factory=lambda: unknown("°C"))
    ambient_temp_min_c: Value = field(default_factory=lambda: unknown("°C"))
    ambient_temp_max_c: Value = field(default_factory=lambda: unknown("°C"))
    ambient_rh_min_percent: Value = field(default_factory=lambda: unknown("%"))
    ambient_rh_max_percent: Value = field(default_factory=lambda: unknown("%"))
    dew_point_margin_k: Value = field(default_factory=lambda: unknown("K"))
    """Минимальное превышение температуры основания над точкой росы."""
    substrate_moisture_max_percent: Value = field(default_factory=lambda: unknown("%"))
    """Массовая влажность основания, метод указывается в ``note``."""
    substrate_ph_max: Value = field(default_factory=lambda: unknown(""))
    pull_off_strength_min_mpa: Value = field(default_factory=lambda: unknown("МПа"))

    def as_dict(self) -> dict[str, Value]:
        return dict(self.__dict__)

    @classmethod
    def from_json(cls, raw: dict[str, Any] | None) -> "ApplicationLimits":
        raw = raw or {}
        known = {f for f in cls().as_dict()}
        unexpected = set(raw) - known
        if unexpected:
            raise ValueError(f"неизвестные поля в application: {sorted(unexpected)}")
        return cls(**{k: Value.from_json(v) for k, v in raw.items()})


@dataclass
class CureProfile:
    """Времена при опорной температуре. Пересчёт на другие — в ``application.py``."""

    reference_temp_c: Value = field(default_factory=lambda: unknown("°C"))
    reference_rh_percent: Value = field(default_factory=lambda: unknown("%"))
    tack_free_h: Value = field(default_factory=lambda: unknown("ч"))
    overcoat_min_h: Value = field(default_factory=lambda: unknown("ч"))
    overcoat_max_h: Value = field(default_factory=lambda: unknown("ч"))
    """Верхняя граница межслойного окна: позже нужна механическая подготовка."""
    foot_traffic_h: Value = field(default_factory=lambda: unknown("ч"))
    full_cure_d: Value = field(default_factory=lambda: unknown("сут"))
    pot_life_min: Value = field(default_factory=lambda: unknown("мин"))

    def as_dict(self) -> dict[str, Value]:
        return dict(self.__dict__)

    @classmethod
    def from_json(cls, raw: dict[str, Any] | None) -> "CureProfile":
        raw = raw or {}
        known = {f for f in cls().as_dict()}
        unexpected = set(raw) - known
        if unexpected:
            raise ValueError(f"неизвестные поля в cure: {sorted(unexpected)}")
        return cls(**{k: Value.from_json(v) for k, v in raw.items()})


@dataclass
class Consumption:
    """Расход на слой и толщина плёнки."""

    per_coat_kg_m2: Value = field(default_factory=lambda: unknown("кг/м²"))
    total_kg_m2: Value = field(default_factory=lambda: unknown("кг/м²"))
    coats: Value = field(default_factory=lambda: unknown("шт"))
    dft_per_coat_mm: Value = field(default_factory=lambda: unknown("мм"))
    solids_by_volume_percent: Value = field(default_factory=lambda: unknown("%"))

    def as_dict(self) -> dict[str, Value]:
        return dict(self.__dict__)

    @classmethod
    def from_json(cls, raw: dict[str, Any] | None) -> "Consumption":
        raw = raw or {}
        known = {f for f in cls().as_dict()}
        unexpected = set(raw) - known
        if unexpected:
            raise ValueError(f"неизвестные поля в consumption: {sorted(unexpected)}")
        return cls(**{k: Value.from_json(v) for k, v in raw.items()})


@dataclass
class Material:
    """Карточка продукта.

    ``family`` и ``roles`` — единственные поля, которые обязаны быть заполнены
    при заведении карточки: без них материал не участвует в проверке
    совместимости. Всё остальное может быть ``unknown``, и это нормальное
    состояние новой записи.
    """

    id: str
    name: str
    manufacturer: str
    family: Family
    roles: tuple[Role, ...]
    cure_mode: CureMode = CureMode.MOISTURE
    components: int = 1
    tds: "TdsRef | None" = None
    application: ApplicationLimits = field(default_factory=ApplicationLimits)
    cure: CureProfile = field(default_factory=CureProfile)
    consumption: Consumption = field(default_factory=Consumption)
    substrates: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    status_note: str | None = None

    def all_values(self) -> dict[str, Value]:
        out: dict[str, Value] = {}
        for prefix, block in (
            ("application", self.application.as_dict()),
            ("cure", self.cure.as_dict()),
            ("consumption", self.consumption.as_dict()),
        ):
            for k, v in block.items():
                out[f"{prefix}.{k}"] = v
        return out

    def gaps(self) -> list[Gap]:
        return collect_gaps(self.id, self.all_values())

    def readiness(self) -> "Readiness":
        """Насколько карточка готова к тому, чтобы на неё опирались на объекте."""
        values = self.all_values()
        missing_required = [
            f"application.{name}"
            for name in REQUIRED_APPLICATION_FIELDS
            if not values[f"application.{name}"].known
        ]
        counts: dict[Status, int] = {s: 0 for s in Status}
        for v in values.values():
            counts[v.status] += 1
        return Readiness(
            material_id=self.id,
            total=len(values),
            counts=counts,
            missing_required=tuple(missing_required),
            has_tds=self.tds is not None,
        )


@dataclass(frozen=True)
class TdsRef:
    """Ссылка на конкретную редакцию TDS.

    Редакция обязательна: параметры меняются между версиями молча, и «данные из
    TDS» без указания какой именно — это данные неизвестного возраста.
    """

    url: str | None = None
    revision: str | None = None
    """Обозначение редакции, как оно напечатано в документе."""
    issued: str | None = None
    retrieved: str | None = None
    local_path: str | None = None

    @property
    def citable(self) -> bool:
        return bool((self.url or self.local_path) and (self.revision or self.issued))

    @classmethod
    def from_json(cls, raw: dict[str, Any] | None) -> "TdsRef | None":
        if not raw:
            return None
        return cls(**raw)


@dataclass(frozen=True)
class Readiness:
    """Сводка по заполненности карточки."""

    material_id: str
    total: int
    counts: dict[Status, int]
    missing_required: tuple[str, ...]
    has_tds: bool

    @property
    def verified_share(self) -> float:
        return self.counts[Status.VERIFIED] / self.total if self.total else 0.0

    @property
    def usable_on_site(self) -> bool:
        """Можно ли по этой карточке принимать решение на объекте."""
        return not self.missing_required and self.counts[Status.VERIFIED] >= len(
            REQUIRED_APPLICATION_FIELDS
        )

    def summary(self) -> str:
        parts = [f"{self.material_id}: заполнено {self.total - self.counts[Status.UNKNOWN]}/{self.total}"]
        parts.append(f"подтверждено {self.counts[Status.VERIFIED]}")
        if self.missing_required:
            parts.append(f"нет ключевых: {', '.join(self.missing_required)}")
        if not self.has_tds:
            parts.append("нет ссылки на TDS")
        return "; ".join(parts)


@dataclass
class SystemLayer:
    """Один слой в проектируемой системе."""

    material: Material
    role: Role
    coats: int = 1
    note: str | None = None


@dataclass
class CoatingSystem:
    """Система «снизу вверх»: от основания к финишу."""

    name: str
    substrate: str
    layers: list[SystemLayer] = field(default_factory=list)

    def pairs(self) -> Iterable[tuple[SystemLayer, SystemLayer]]:
        """Соседние пары слоёв — именно на стыках возникает несовместимость."""
        return zip(self.layers, self.layers[1:])
