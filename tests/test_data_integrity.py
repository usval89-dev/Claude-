"""Проверки самих данных, а не кода.

С ростом числа карточек ошибки переезжают из логики в JSON: опечатка в
семействе, карточка без ссылки на документ, продукт, заявленный готовым к
применению без единого подтверждённого параметра.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from matdb.loader import DATA_DIR, load
from matdb.models import Family
from matdb.values import Status


@pytest.fixture(scope="module")
def db():
    return load()


def test_every_used_family_is_documented(db):
    """Семейство, к которому отнесён продукт, обязано быть описано."""
    for material in db:
        assert material.family.value in db.families, (
            f"{material.id}: семейство {material.family.value} не описано "
            "в data/families.json"
        )


def test_families_json_has_no_unknown_entries(db):
    for name in db.families:
        Family(name)


def test_family_entries_carry_cure_mode_and_notes(db):
    for name, entry in db.families.items():
        assert entry.get("cure_mode"), f"{name}: не указан механизм отверждения"
        assert entry.get("notes"), f"{name}: нет ни одного примечания"


def test_every_card_points_at_a_document(db):
    """Карточка без адреса документа не попадает в очередь на заполнение."""
    for material in db:
        assert material.tds is not None, f"{material.id}: нет ссылки на документ"
        assert material.tds.url, f"{material.id}: ссылка пустая"


def test_cards_without_data_are_marked_as_such(db):
    for material in db:
        if not material.readiness().usable_on_site:
            assert material.status_note, (
                f"{material.id}: непригодна для применения, но не помечена"
            )


def test_no_card_claims_verified_data_without_a_person(db):
    """Страховка поверх проверок в Value: verified без имени недопустим."""
    for material in db:
        for name, value in material.all_values().items():
            if value.status is Status.VERIFIED:
                assert value.verified_by, f"{material.id}.{name}: verified без имени"


def test_unretrieved_documents_are_not_citable(db):
    """Ссылка без редакции честно считается непригодной для цитирования."""
    for material in db:
        if material.tds and not material.tds.retrieved:
            assert not material.tds.citable, (
                f"{material.id}: документ не скачан, но ссылка считается цитируемой"
            )


def test_card_ids_are_slugs():
    for path in (DATA_DIR / "materials").glob("*.json"):
        if path.name.startswith("_"):
            continue
        assert path.stem.replace("-", "").isalnum(), (
            f"{path.name}: id должен быть латинским слагом через дефис"
        )


def test_no_placeholder_numbers_leaked_into_data():
    """Ни в одной карточке не должно быть чисел без источника.

    Загрузчик это и так проверяет, но тест фиксирует требование на уровне
    файлов: значения из поисковой выдачи и «примерно такие» цифры в данных
    неотличимы от извлечённых из документа.
    """
    for path in (DATA_DIR / "materials").glob("*.json"):
        if path.name.startswith("_"):
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        for block in ("application", "cure", "consumption"):
            for name, entry in (raw.get(block) or {}).items():
                assert isinstance(entry, dict), (
                    f"{path.name}: {block}.{name} записано голым числом"
                )
                assert entry.get("source"), (
                    f"{path.name}: {block}.{name} без ссылки на источник"
                )


def test_fetch_queue_documents_the_blocked_access():
    """Очередь на загрузку обязана объяснять, почему документов нет."""
    text = (Path(DATA_DIR).parent / "docs" / "FETCH_QUEUE.md").read_text(encoding="utf-8")
    assert "не открыт" in text
    assert "FETCH_QUEUE" not in text.split("\n")[0]


def test_bitumen_modified_pu_differs_from_plain_pu_over_bitumen(db):
    """Смысл выделения семейства: вердикт по битуму должен отличаться."""
    plain = db.compatibility.resolve(Family.PU_1K_MOISTURE, Family.BITUMEN)
    modified = db.compatibility.resolve(Family.PU_BITUMEN, Family.BITUMEN)
    assert plain.verdict is not modified.verdict


def test_bitumen_modified_pu_warns_about_migration_upward(db):
    """Семейство рассчитано на битум снизу, но само отдаёт битум наверх."""
    res = db.compatibility.resolve(Family.PU_1K_MOISTURE, Family.PU_BITUMEN)
    assert "мигрировать" in res.rationale


def test_waterborne_pu_has_its_own_rules(db):
    res = db.compatibility.resolve(Family.PU_1K_WB, Family.PU_1K_MOISTURE)
    assert res.conditions
    assert any("осадк" in c for c in res.conditions), (
        "для состава на водной основе риск смыва до высыхания должен быть назван"
    )


def test_every_family_with_products_has_at_least_one_rule(db):
    """Семейство без единого правила — дыра в справочнике совместимости."""
    covered = set()
    for rule in db.compatibility.rules:
        for side in (rule.over, rule.under):
            kind, _, name = side.partition(":")
            if kind == "family":
                covered.add(name)
    used = {m.family.value for m in db}
    missing = sorted(used - covered)
    assert not missing, f"семейства без правил совместимости: {missing}"
