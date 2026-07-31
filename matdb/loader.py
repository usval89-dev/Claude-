"""Загрузка и валидация данных из ``data/``."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .compat import CompatibilityIndex, Rule
from .models import (
    ApplicationLimits,
    Consumption,
    CureMode,
    CureProfile,
    Family,
    Material,
    Role,
    TdsRef,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class DataError(ValueError):
    """Ошибка в данных, а не в коде. Сообщение адресовано тому, кто правит JSON."""


def _enum(cls: Any, raw: str, where: str) -> Any:
    try:
        return cls(raw)
    except ValueError:
        allowed = ", ".join(m.value for m in cls)
        raise DataError(f"{where}: неизвестное значение {raw!r}; допустимо: {allowed}")


def material_from_json(raw: dict[str, Any], where: str) -> Material:
    for required in ("id", "name", "manufacturer", "family", "roles"):
        if required not in raw:
            raise DataError(f"{where}: отсутствует обязательное поле {required!r}")
    mid = raw["id"]
    try:
        return Material(
            id=mid,
            name=raw["name"],
            manufacturer=raw["manufacturer"],
            family=_enum(Family, raw["family"], f"{where}.family"),
            roles=tuple(_enum(Role, r, f"{where}.roles") for r in raw["roles"]),
            cure_mode=_enum(CureMode, raw.get("cure_mode", "moisture"), f"{where}.cure_mode"),
            components=int(raw.get("components", 1)),
            tds=TdsRef.from_json(raw.get("tds")),
            application=ApplicationLimits.from_json(raw.get("application")),
            cure=CureProfile.from_json(raw.get("cure")),
            consumption=Consumption.from_json(raw.get("consumption")),
            substrates=tuple(raw.get("substrates", ())),
            tags=tuple(raw.get("tags", ())),
            aliases=tuple(raw.get("aliases", ())),
            status_note=raw.get("status_note"),
        )
    except (ValueError, TypeError) as exc:
        if isinstance(exc, DataError):
            raise
        raise DataError(f"{where}: {exc}") from exc


@dataclass
class Database:
    materials: dict[str, Material] = field(default_factory=dict)
    compatibility: CompatibilityIndex = field(default_factory=CompatibilityIndex)
    families: dict[str, Any] = field(default_factory=dict)

    def __iter__(self) -> Iterator[Material]:
        return iter(self.materials.values())

    def __len__(self) -> int:
        return len(self.materials)

    def get(self, key: str) -> Material:
        """Найти материал по id или псевдониму."""
        if key in self.materials:
            return self.materials[key]
        for m in self.materials.values():
            if key in m.aliases or key.lower() == m.name.lower():
                return m
        raise KeyError(f"материал {key!r} не найден; известно {len(self.materials)} шт.")

    def gaps(self) -> list[str]:
        out: list[str] = []
        for m in sorted(self.materials.values(), key=lambda x: x.id):
            out.extend(str(g) for g in m.gaps())
        return out


def load(data_dir: Path | str = DATA_DIR) -> Database:
    """Прочитать базу целиком. Любая ошибка данных — исключение, не молчание."""
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise DataError(f"каталог данных не найден: {data_dir}")

    db = Database()

    families_path = data_dir / "families.json"
    if families_path.exists():
        db.families = json.loads(families_path.read_text(encoding="utf-8")).get(
            "families", {}
        )
        for name in db.families:
            _enum(Family, name, "families.json")

    materials_dir = data_dir / "materials"
    if materials_dir.is_dir():
        for path in sorted(materials_dir.glob("*.json")):
            if path.name.startswith("_"):
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
            material = material_from_json(raw, path.name)
            if material.id in db.materials:
                raise DataError(f"{path.name}: дублирующийся id {material.id!r}")
            if material.id != path.stem:
                raise DataError(
                    f"{path.name}: id {material.id!r} не совпадает с именем файла"
                )
            db.materials[material.id] = material

    rules_path = data_dir / "compatibility_rules.json"
    if rules_path.exists():
        raw_rules = json.loads(rules_path.read_text(encoding="utf-8")).get("rules", [])
        for i, raw_rule in enumerate(raw_rules):
            try:
                rule = Rule.from_json(raw_rule)
            except (KeyError, ValueError) as exc:
                raise DataError(f"compatibility_rules.json[{i}]: {exc}") from exc
            for side in (rule.over, rule.under):
                _validate_ref(side, db, f"compatibility_rules.json[{i}]")
            db.compatibility.add(rule)

    return db


def _validate_ref(ref: str, db: Database, where: str) -> None:
    """Ссылка в правиле должна указывать на существующее семейство или продукт."""
    kind, _, name = ref.partition(":")
    if kind == "family":
        _enum(Family, name, f"{where}: {ref}")
    elif kind == "product":
        if name not in db.materials:
            raise DataError(f"{where}: правило ссылается на неизвестный продукт {name!r}")
    else:
        raise DataError(
            f"{where}: ссылка {ref!r} должна начинаться с 'family:' или 'product:'"
        )
