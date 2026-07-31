#!/usr/bin/env python3
"""Завести карточку материала из шаблона.

    python tools/new_material.py --id isomat-isoflex-pu-500 \
        --name "ISOFLEX-PU 500" --manufacturer ISOMAT \
        --family pu_1k_moisture --role membrane

Создаёт файл только с полями идентификации. Числовые параметры заполняются
вручную из открытого TDS — см. docs/TDS_CHECKLIST.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from matdb.models import CureMode, Family, Role  # noqa: E402

#: Механизм отверждения, характерный для семейства, — подставляется по умолчанию.
DEFAULT_CURE_MODE = {
    Family.PU_1K_MOISTURE: CureMode.MOISTURE,
    Family.PU_2K: CureMode.CHEMICAL,
    Family.PU_CEMENT: CureMode.HYDRATION,
    Family.EPOXY_2K: CureMode.CHEMICAL,
    Family.EPOXY_WB: CureMode.CHEMICAL,
    Family.PMMA: CureMode.CHEMICAL,
    Family.POLYUREA: CureMode.CHEMICAL,
    Family.ACRYLIC_WB: CureMode.EVAPORATION,
    Family.BITUMEN: CureMode.EVAPORATION,
    Family.BITUMEN_POLYMER: CureMode.EVAPORATION,
    Family.CEMENTITIOUS: CureMode.HYDRATION,
    Family.CEMENTITIOUS_POLYMER: CureMode.HYDRATION,
    Family.SILICATE: CureMode.CHEMICAL,
    Family.SILANE_SILOXANE: CureMode.CHEMICAL,
    Family.MS_POLYMER: CureMode.MOISTURE,
    Family.SILICONE: CureMode.MOISTURE,
}

NOTE = (
    "Карточка заведена без TDS: заполнены только поля идентификации. "
    "Числовые параметры извлекаются из документа вручную — см. docs/TDS_CHECKLIST.md."
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--id", required=True, help="идентификатор, он же имя файла")
    p.add_argument("--name", required=True, help="торговое наименование как в TDS")
    p.add_argument("--manufacturer", required=True)
    p.add_argument("--family", required=True, choices=[f.value for f in Family])
    p.add_argument(
        "--role", required=True, action="append", choices=[r.value for r in Role],
        help="можно указать несколько раз",
    )
    p.add_argument("--components", type=int, default=1)
    p.add_argument("--tds-url", default=None)
    p.add_argument("--force", action="store_true", help="перезаписать существующий файл")
    args = p.parse_args(argv)

    family = Family(args.family)
    path = REPO / "data" / "materials" / f"{args.id}.json"
    if path.exists() and not args.force:
        print(f"Файл уже существует: {path}. Используйте --force для перезаписи.", file=sys.stderr)
        return 1

    card = {
        "id": args.id,
        "name": args.name,
        "manufacturer": args.manufacturer,
        "family": family.value,
        "roles": args.role,
        "cure_mode": DEFAULT_CURE_MODE.get(family, CureMode.CHEMICAL).value,
        "components": args.components,
        "status_note": NOTE,
        "tds": {"url": args.tds_url} if args.tds_url else None,
        "application": {},
        "cure": {},
        "consumption": {},
        "substrates": [],
        "tags": [],
    }
    path.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Создано: {path.relative_to(REPO)}")
    print("Дальше: открыть TDS и заполнить поля по docs/TDS_CHECKLIST.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
