#!/usr/bin/env python3
"""Разобрать TDS в черновик карточки.

    python tools/extract_tds.py tds/isomat/isoflex-pu-500.pdf \
        --id isoflex-pu-500 --revision 2024-03

Печатает отчёт со ссылкой на страницу и цитатой на каждое найденное число.
С ``--write`` дописывает найденное в карточку ``data/materials/<id>.json``,
не затирая то, что уже проставлено руками.

Ничего не получает статус ``verified``: это делает человек, сверив цитаты с
документом.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from matdb.extract import extract  # noqa: E402


def read_pdf(path: Path) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit(
            "Нужен pypdf: python -m pip install pypdf\n"
            "Либо подайте текст: pdftotext -layout file.pdf - | "
            "python tools/extract_tds.py - --id …"
        )
    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    if not any(p.strip() for p in pages):
        raise SystemExit(
            f"{path.name}: текст не извлекается. Вероятно, это скан — "
            "нужен OCR, автоматический разбор здесь бесполезен."
        )
    return pages


def read_text(path: Path) -> list[str]:
    """Текстовый файл: страницы разделяются символом перевода страницы."""
    raw = sys.stdin.read() if str(path) == "-" else path.read_text(encoding="utf-8")
    return raw.split("\f")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("document", type=Path, help="PDF, текстовый файл или - для stdin")
    p.add_argument("--id", required=True, help="id карточки в data/materials")
    p.add_argument(
        "--revision",
        default=None,
        help="редакция документа, как напечатана в нём; без неё ссылка на источник "
        "не даёт понять возраст данных",
    )
    p.add_argument("--write", action="store_true", help="дописать найденное в карточку")
    args = p.parse_args(argv)

    if str(args.document) != "-" and not args.document.exists():
        print(f"Файл не найден: {args.document}", file=sys.stderr)
        return 2

    if args.document.suffix.lower() == ".pdf":
        pages = read_pdf(args.document)
    else:
        pages = read_text(args.document)

    source_id = f"{args.id}@{args.revision}" if args.revision else args.id
    result = extract(pages, source_id)
    print(result.report())

    if not args.revision:
        print(
            "\nВНИМАНИЕ: редакция документа не указана (--revision). Производители "
            "меняют параметры между версиями молча, и ссылка без редакции — это "
            "ссылка на данные неизвестного возраста."
        )

    if not args.write:
        print("\nЗапуск без --write: карточка не изменена.")
        return 0

    card_path = REPO / "data" / "materials" / f"{args.id}.json"
    if not card_path.exists():
        print(
            f"\nКарточки {card_path.relative_to(REPO)} нет. Создайте её сначала:\n"
            f"  python tools/new_material.py --id {args.id} --name … "
            f"--manufacturer … --family … --role …",
            file=sys.stderr,
        )
        return 2

    card = json.loads(card_path.read_text(encoding="utf-8"))
    updated = result.to_card(card)
    card_path.write_text(
        json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\nЗаписано в {card_path.relative_to(REPO)}.")
    print(
        "Дальше — сверка человеком: открыть документ, проверить каждую цитату, "
        "заменить status на verified и проставить verified_by/verified_at."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
