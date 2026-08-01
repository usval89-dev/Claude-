"""Командная строка: ``python -m matdb <команда>``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .application import Severity, check_application, cure_schedule
from .compat import Compat
from .loader import DATA_DIR, Database, DataError, load
from .models import REQUIRED_APPLICATION_FIELDS, Family
from .psychro import PsychroRangeError, measure
from .values import Status


def _db(args: argparse.Namespace) -> Database:
    return load(args.data)


def cmd_dew(args: argparse.Namespace) -> int:
    p = measure(args.air, args.rh, args.surface)
    print(f"Воздух:                 {p.t_air_c:.1f} °C, {p.rh_percent:.0f} %")
    print(f"Основание:              {p.t_surface_c:.1f} °C")
    print(f"Точка росы:             {p.dew_point_c:.1f} °C")
    print(f"Запас над точкой росы:  {p.delta_to_dew_point_k:+.1f} K")
    print(f"Влажность у поверхности:{p.surface_rh_percent:6.0f} %")
    print(f"Абсолютная влажность:   {p.absolute_humidity_g_m3:.1f} г/м³")
    print(f"Влагосодержание:        {p.mixing_ratio_g_kg:.1f} г/кг")
    print(f"Парциальное давление:   {p.vapour_pressure_hpa:.1f} гПа")
    if p.wet_bulb_c is not None:
        print(f"Мокрый термометр:       {p.wet_bulb_c:.1f} °C")
    if p.condensing:
        print("\nОснование холоднее точки росы — конденсация идёт прямо сейчас.")
    elif p.delta_to_dew_point_k < 3:
        print("\nЗапас меньше 3 K — по общему правилу наносить нельзя.")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    db = _db(args)
    material = db.get(args.material)
    verdict = check_application(
        material,
        t_air_c=args.air,
        rh_percent=args.rh,
        t_surface_c=args.surface,
        substrate_moisture_percent=args.moisture,
        expected_temp_drop_k=args.drop,
    )
    print(verdict.report())
    if material.status_note:
        print(f"\nПримечание к карточке: {material.status_note}")
    total = len(verdict.checks)
    no_data = sum(1 for c in verdict.checks if c.severity is Severity.NO_DATA)
    unverified = sum(
        1 for c in verdict.checks if c.basis and c.basis is not Status.VERIFIED
    )
    notes = []
    if no_data:
        notes.append(f"{no_data} из {total} проверок не выполнены — нет данных в карточке")
    if unverified:
        notes.append(
            f"{unverified} из {total} опираются на неподтверждённые значения"
        )
    if notes:
        print("\n" + "; ".join(notes) + ".")
        print("Расчёт не заменяет решение человека на объекте.")
    return 0 if verdict.can_apply else 1


def cmd_schedule(args: argparse.Namespace) -> int:
    db = _db(args)
    material = db.get(args.material)
    print(f"{material.name} при температуре основания {args.surface:.0f} °C:")
    for est in cure_schedule(material, args.surface):
        print(f"  {est.render()}")
    return 0


def cmd_compat(args: argparse.Namespace) -> int:
    db = _db(args)

    def side(key: str):
        try:
            return db.get(key)
        except KeyError:
            try:
                return Family(key)
            except ValueError:
                raise DataError(
                    f"{key!r} — не id продукта и не имя семейства"
                )

    res = db.compatibility.resolve(side(args.over), side(args.under))
    print(res.render())
    return 0 if res.verdict is Compat.COMPATIBLE else 1


def cmd_gaps(args: argparse.Namespace) -> int:
    db = _db(args)
    materials = sorted(db, key=lambda m: m.id)
    if args.family:
        materials = [m for m in materials if m.family.value == args.family]
        if not materials:
            print(f"Нет материалов семейства {args.family}.")
            return 0

    if args.all:
        total = 0
        for material in materials:
            lines = [str(g) for g in material.gaps()]
            total += len(lines)
            for line in lines:
                print(f"  {line}")
        print(f"\nВсего незаполненных параметров: {total}")
        return 0

    # По умолчанию — только ключевые поля: полный список из сотен строк
    # не является рабочей очередью, он является шумом.
    empty: list[str] = []
    partial: list[tuple[str, list[str]]] = []
    for material in materials:
        r = material.readiness()
        if r.counts[Status.UNKNOWN] == r.total:
            empty.append(material.id)
        elif r.missing_required:
            partial.append((material.id, list(r.missing_required)))

    if partial:
        print("Начаты, но не хватает ключевых полей:\n")
        for mid, missing in partial:
            print(f"  {mid}")
            for f in missing:
                print(f"      {f}")
        print()
    if empty:
        print(f"Пусты, заполнены только идентификация ({len(empty)}):")
        print("      " + ", ".join(empty))
        print()
    if not partial and not empty:
        print("Ключевые поля заполнены во всех карточках.")
        return 0
    print(
        f"Ключевых полей на карточку: {len(REQUIRED_APPLICATION_FIELDS)}. "
        "Полный список всех пробелов: --all"
    )
    return 0


def cmd_queue(args: argparse.Namespace) -> int:
    """Очередь на загрузку: какие документы нужны и куда их класть."""
    db = _db(args)
    pending = [
        m for m in sorted(db, key=lambda x: (x.manufacturer, x.id))
        if not m.readiness().usable_on_site
    ]
    if not pending:
        print("Все карточки заполнены и подтверждены.")
        return 0

    by_mfr: dict[str, list] = {}
    for material in pending:
        by_mfr.setdefault(material.manufacturer, []).append(material)

    print(f"Документов к загрузке: {len(pending)}\n")
    for mfr, materials in by_mfr.items():
        print(f"{mfr}")
        for m in materials:
            url = m.tds.url if m.tds else None
            print(f"  {m.id}  ({m.family.value})")
            print(f"      {url or 'адрес документа не найден'}")
        print()
    print("Порядок работы с каждым документом:")
    print("  1. Скачать в tds/<производитель>/<продукт>.pdf")
    print("  2. python tools/extract_tds.py <файл> --id <id> --revision <редакция> --write")
    print("  3. Сверить цитаты из отчёта с документом")
    print("  4. Проставить status=verified, verified_by, verified_at")
    print("\nШаг 4 не автоматизируется: ответственность за число берёт тот, кто его подтвердил.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    db = _db(args)
    if not db:
        print("В базе нет ни одного материала.")
        return 0
    print(f"Материалов: {len(db)}, правил совместимости: {len(db.compatibility.rules)}")

    by_family: dict[str, list[str]] = {}
    for material in db:
        by_family.setdefault(material.family.value, []).append(material.id)
    print("\nПо семействам:")
    for family, ids in sorted(by_family.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        print(f"  {family:<24} {len(ids)}")

    started = [m for m in sorted(db, key=lambda x: x.id)
               if m.readiness().counts[Status.UNKNOWN] < m.readiness().total]
    usable = [m for m in db if m.readiness().usable_on_site]
    if started:
        print("\nС заполненными параметрами:")
        for material in started:
            print(f"  {material.readiness().summary()}")

    print(
        f"\nЗаготовок без единого параметра: {len(db) - len(started)} из {len(db)}."
        f"\nПригодны для решения на объекте: {len(usable)} из {len(db)}."
    )
    if not usable:
        print(
            "\nНи по одной карточке нельзя давать рекомендацию: числовых данных нет. "
            "Очередь на загрузку документов — docs/FETCH_QUEUE.md."
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="matdb", description="База материалов и расчёт условий нанесения"
    )
    p.add_argument("--data", type=Path, default=DATA_DIR, help="каталог с данными")
    sub = p.add_subparsers(dest="command", required=True)

    dew = sub.add_parser("dew", help="точка росы и производные величины")
    dew.add_argument("--air", type=float, required=True, help="температура воздуха, °C")
    dew.add_argument("--rh", type=float, required=True, help="влажность воздуха, %%")
    dew.add_argument("--surface", type=float, required=True, help="температура основания, °C")
    dew.set_defaults(func=cmd_dew)

    check = sub.add_parser("check", help="можно ли наносить материал в этих условиях")
    check.add_argument("material")
    check.add_argument("--air", type=float, required=True)
    check.add_argument("--rh", type=float, required=True)
    check.add_argument("--surface", type=float, required=True)
    check.add_argument("--moisture", type=float, default=None, help="влажность основания, %%")
    check.add_argument(
        "--drop", type=float, default=0.0, help="ожидаемое остывание основания до отлипа, K"
    )
    check.set_defaults(func=cmd_check)

    sched = sub.add_parser("schedule", help="график отверждения при фактической температуре")
    sched.add_argument("material")
    sched.add_argument("--surface", type=float, required=True)
    sched.set_defaults(func=cmd_schedule)

    compat = sub.add_parser("compat", help="совместимость: что кладём на что")
    compat.add_argument("over", help="верхний слой: id продукта или имя семейства")
    compat.add_argument("under", help="нижний слой: id продукта или имя семейства")
    compat.set_defaults(func=cmd_compat)

    gaps = sub.add_parser("gaps", help="очередь на извлечение из TDS")
    gaps.add_argument("--all", action="store_true", help="все пробелы, а не только ключевые")
    gaps.add_argument("--family", default=None, help="ограничить одним семейством")
    gaps.set_defaults(func=cmd_gaps)

    status = sub.add_parser("status", help="готовность карточек")
    status.set_defaults(func=cmd_status)

    queue = sub.add_parser("queue", help="очередь на загрузку документов")
    queue.set_defaults(func=cmd_queue)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (DataError, KeyError, PsychroRangeError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
