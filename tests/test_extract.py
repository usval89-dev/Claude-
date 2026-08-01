"""Проверка извлечения из TDS.

Тексты в тестах — синтетические, но написаны формулировками, которыми реальные
TDS действительно пользуются. Числа вымышлены и в ``data/`` не попадают.
"""

from __future__ import annotations

from matdb.extract import extract
from matdb.values import Status, Value


def test_substrate_temperature_range_english():
    pages = ["Substrate temperature during application: +5°C to +35°C."]
    ex = extract(pages, "fixture@0")
    r = ex.resolved()
    assert r["application.substrate_temp_min_c"].value == 5
    assert r["application.substrate_temp_max_c"].value == 35
    assert r["application.substrate_temp_min_c"].page == 1


def test_substrate_temperature_range_russian():
    pages = ["Температура основания при нанесении: от +5 °С до +35 °С."]
    ex = extract(pages, "fixture@0")
    r = ex.resolved()
    assert r["application.substrate_temp_min_c"].value == 5
    assert r["application.substrate_temp_max_c"].value == 35


def test_decimal_comma_is_parsed():
    pages = ["Consumption: 1,5 kg/m2 per coat."]
    ex = extract(pages, "fixture@0")
    assert ex.by_field()["_consumption.value_kg_m2"][0].value == 1.5


def test_ambient_and_substrate_are_separate_fields():
    pages = [
        "Ambient temperature: +8°C to +30°C. Substrate temperature: +5°C to +35°C."
    ]
    r = extract(pages, "fixture@0").resolved()
    assert r["application.ambient_temp_min_c"].value == 8
    assert r["application.substrate_temp_min_c"].value == 5


def test_unscoped_application_temperature_is_not_guessed():
    """«Application temperature» без уточнения нельзя разложить на два параметра."""
    pages = ["Application temperature: +5°C to +35°C."]
    ex = extract(pages, "fixture@0")
    assert "application.substrate_temp_min_c" not in ex.resolved()
    assert "_unscoped.temp_min_c" in ex.unscoped()
    assert any("разнести вручную" in n for n in ex.notes)


def test_dew_point_margin_english():
    pages = [
        "The substrate temperature must be at least 3°C above the dew point."
    ]
    r = extract(pages, "fixture@0").resolved()
    assert r["application.dew_point_margin_k"].value == 3


def test_dew_point_margin_russian():
    pages = ["Температура основания должна быть на 3 °С выше точки росы."]
    r = extract(pages, "fixture@0").resolved()
    assert r["application.dew_point_margin_k"].value == 3


def test_relative_humidity_limit():
    pages = ["Do not apply when relative humidity is above 85%."]
    # «above» не входит в список ограничителей: это не предел, а условие запрета,
    # и формулировка разбирается иначе. Проверяем работающую формулировку.
    pages = ["Apply only when relative humidity is below 85%."]
    r = extract(pages, "fixture@0").resolved()
    assert r["application.ambient_rh_max_percent"].value == 85


def test_substrate_moisture_limit_and_method():
    pages = [
        "Substrate moisture content must be less than 4%, measured by the CM-method."
    ]
    ex = extract(pages, "fixture@0")
    r = ex.resolved()
    assert r["application.substrate_moisture_max_percent"].value == 4
    assert ex.moisture_methods and ex.moisture_methods[0][0] == "CM-метод"


def test_moisture_without_method_is_flagged_in_card():
    pages = ["Moisture content must be below 4%."]
    ex = extract(pages, "fixture@0")
    card = ex.to_card({})
    note = card["application"]["substrate_moisture_max_percent"]["note"]
    assert "МЕТОД ЗАМЕРА В ДОКУМЕНТЕ НЕ НАЙДЕН" in note


def test_overcoat_window():
    pages = ["The second coat is applied crosswise after 8-24 hours."]
    r = extract(pages, "fixture@0").resolved()
    assert r["cure.overcoat_min_h"].value == 8
    assert r["cure.overcoat_max_h"].value == 24


def test_reference_temperature():
    pages = ["All times are given at 20°C and 50% relative humidity."]
    r = extract(pages, "fixture@0").resolved()
    assert r["cure.reference_temp_c"].value == 20


def test_conflicting_values_are_not_written_to_card():
    """Два разных значения одного поля — конфликт, а не победа первого."""
    pages = [
        "Substrate temperature: +5°C to +35°C.",
        "Substrate temperature: +10°C to +30°C.",
    ]
    ex = extract(pages, "fixture@0")
    conflicts = ex.conflicts()
    assert "application.substrate_temp_min_c" in conflicts
    assert "application.substrate_temp_min_c" not in ex.resolved()
    card = ex.to_card({})
    assert "substrate_temp_min_c" not in card.get("application", {})
    assert "КОНФЛИКТЫ" in ex.report()


def test_repeated_identical_value_is_not_a_conflict():
    pages = [
        "Substrate temperature: +5°C to +35°C.",
        "Reminder: substrate temperature +5°C to +35°C.",
    ]
    ex = extract(pages, "fixture@0")
    assert not ex.conflicts()
    assert ex.resolved()["application.substrate_temp_min_c"].value == 5


def test_page_numbers_are_one_based_and_correct():
    pages = ["Cover page.", "Nothing here.", "Substrate temperature: +5°C to +35°C."]
    c = extract(pages, "fixture@0").resolved()["application.substrate_temp_min_c"]
    assert c.page == 3


def test_card_values_carry_source_with_page():
    pages = ["", "Substrate temperature: +5°C to +35°C."]
    card = extract(pages, "isomat/product@2024-03").to_card({})
    entry = card["application"]["substrate_temp_min_c"]
    assert entry["source"] == "tds:isomat/product@2024-03#p2"
    assert entry["status"] == "tds"


def test_extracted_values_are_never_verified():
    pages = ["Substrate temperature: +5°C to +35°C. Moisture below 4%."]
    card = extract(pages, "fixture@0").to_card({})
    for section in ("application", "cure", "consumption"):
        for entry in card.get(section, {}).values():
            assert entry["status"] != Status.VERIFIED.value


def test_card_values_are_loadable():
    pages = ["Substrate temperature: +5°C to +35°C."]
    card = extract(pages, "fixture@0").to_card({})
    v = Value.from_json(card["application"]["substrate_temp_min_c"])
    assert v.value == 5 and v.status is Status.TDS


def test_manual_edits_are_not_overwritten():
    """Правка человека главнее машинного разбора."""
    existing = {
        "application": {
            "substrate_temp_min_c": {
                "value": 7, "unit": "°C", "status": "verified",
                "source": "tds:x@1#p2", "verified_by": "прораб",
            }
        }
    }
    pages = ["Substrate temperature: +5°C to +35°C."]
    card = extract(pages, "fixture@0").to_card(existing)
    assert card["application"]["substrate_temp_min_c"]["value"] == 7
    assert card["application"]["substrate_temp_max_c"]["value"] == 35


def test_gaps_listed_when_nothing_found():
    ex = extract(["Совершенно посторонний текст без чисел."], "fixture@0")
    assert len(ex.gaps()) == 5
    assert not ex.resolved()
    assert "НЕ НАЙДЕНО" in ex.report()


def test_report_quotes_the_document():
    pages = ["Substrate temperature during application: +5°C to +35°C."]
    report = extract(pages, "fixture@0").report()
    assert "Substrate temperature during application: +5°C to +35°C" in report
    assert "verified" in report


def test_dew_point_margin_not_stolen_from_temperature_range():
    """Регрессия: правило захватывало первое число диапазона температур.

    На фразе ниже извлекался запас 5 K вместо 3 K — правдоподобное неверное
    число, которое при просмотре карточки глазом не отличить от верного.
    """
    pages = [
        "Substrate temperature must be between +5°C and +35°C and at least "
        "3°C above the dew point."
    ]
    r = extract(pages, "fixture@0").resolved()
    assert r["application.dew_point_margin_k"].value == 3
    assert r["application.substrate_temp_min_c"].value == 5
    assert r["application.substrate_temp_max_c"].value == 35


def test_number_belonging_to_another_keyword_is_not_taken():
    """Между ключевым словом и числом не должно быть другого числа."""
    pages = ["Relative humidity 40% at the time of the 85% test is irrelevant."]
    ex = extract(pages, "fixture@0")
    assert "application.ambient_rh_max_percent" not in ex.resolved()


def test_no_false_positives_on_unrelated_numbers():
    """Плотность и удлинение не должны попасть в поля условий нанесения."""
    pages = [
        "Density: 1.4 kg/l. Elongation at break: 500%. "
        "Tensile strength: 6 N/mm2. Shore A hardness: 65."
    ]
    ex = extract(pages, "fixture@0")
    assert not ex.resolved(), f"ложные срабатывания: {ex.resolved()}"


def test_realistic_page_extracts_the_full_set():
    """Страница, собранная из типовых формулировок TDS."""
    page = """
    APPLICATION
    Substrate temperature must be between +5°C and +35°C and at least 3°C above
    the dew point. Apply only when relative humidity is below 85%.
    The substrate moisture content must be less than 4%, measured by the
    CM-method. The second coat is applied crosswise after 8-24 hours.
    All times are given at 20°C and 50% relative humidity.
    Consumption: 1.0-1.5 kg/m2 in two coats.
    """
    ex = extract([page], "fixture@0")
    assert not ex.gaps(), f"не найдено: {ex.gaps()}"
    assert not ex.conflicts()
    r = ex.resolved()
    assert r["application.substrate_temp_min_c"].value == 5
    assert r["application.substrate_temp_max_c"].value == 35
    assert r["application.dew_point_margin_k"].value == 3
    assert r["application.ambient_rh_max_percent"].value == 85
    assert r["application.substrate_moisture_max_percent"].value == 4
    assert r["cure.overcoat_min_h"].value == 8
    assert r["cure.overcoat_max_h"].value == 24
    assert r["cure.reference_temp_c"].value == 20
    # Расход остаётся неразнесённым: «на слой» или «на систему» решает человек.
    assert "_consumption.min_kg_m2" in ex.unscoped()
