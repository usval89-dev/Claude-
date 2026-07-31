"""Загрузчик обязан ругаться на плохие данные, а не проглатывать их."""

from __future__ import annotations

import json

import pytest

from matdb.loader import DataError, load, material_from_json
from matdb.models import Family, Role
from matdb.values import Status


def test_repository_data_loads():
    db = load()
    assert len(db) >= 1
    assert db.compatibility.rules


def test_every_rule_reference_resolves():
    # Загрузчик уже проверяет это, но тест фиксирует требование явно.
    db = load()
    for rule in db.compatibility.rules:
        for side in (rule.over, rule.under):
            kind, _, name = side.partition(":")
            if kind == "family":
                Family(name)
            else:
                assert name in db.materials


def test_template_is_not_loaded_as_material():
    db = load()
    assert "manufacturer-product-slug" not in db.materials


def test_seeded_cards_are_honest_about_being_empty():
    db = load()
    for material in db:
        readiness = material.readiness()
        if not readiness.usable_on_site:
            assert material.status_note, (
                f"{material.id}: карточка не готова к применению, но не помечена "
                "примечанием о своём состоянии"
            )


def test_material_requires_identity_fields():
    with pytest.raises(DataError, match="family"):
        material_from_json({"id": "x", "name": "X", "manufacturer": "Y", "roles": []}, "x")


def test_unknown_family_is_rejected_with_hint():
    raw = {"id": "x", "name": "X", "manufacturer": "Y", "family": "магия", "roles": ["membrane"]}
    with pytest.raises(DataError, match="допустимо"):
        material_from_json(raw, "x.json")


def test_unknown_application_field_is_rejected():
    # Опечатка в имени поля не должна тихо терять данные.
    raw = {
        "id": "x",
        "name": "X",
        "manufacturer": "Y",
        "family": "pu_1k_moisture",
        "roles": ["membrane"],
        "application": {"substrate_temp_minimum_c": {"value": 5, "status": "reference"}},
    }
    with pytest.raises(DataError, match="неизвестные поля"):
        material_from_json(raw, "x.json")


def test_bare_number_in_data_is_rejected():
    raw = {
        "id": "x",
        "name": "X",
        "manufacturer": "Y",
        "family": "pu_1k_moisture",
        "roles": ["membrane"],
        "application": {"substrate_temp_min_c": 5},
    }
    with pytest.raises(DataError, match="без происхождения"):
        material_from_json(raw, "x.json")


def test_id_must_match_filename(tmp_path):
    (tmp_path / "materials").mkdir()
    (tmp_path / "materials" / "alpha.json").write_text(
        json.dumps(
            {
                "id": "beta",
                "name": "Beta",
                "manufacturer": "Y",
                "family": "pu_1k_moisture",
                "roles": ["membrane"],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(DataError, match="не совпадает с именем файла"):
        load(tmp_path)


def test_rule_pointing_at_missing_product_is_rejected(tmp_path):
    (tmp_path / "materials").mkdir()
    (tmp_path / "compatibility_rules.json").write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "over": "product:не-существует",
                        "under": "family:bitumen",
                        "verdict": "incompatible",
                        "rationale": "…",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(DataError, match="неизвестный продукт"):
        load(tmp_path)


def test_lookup_by_alias_and_name():
    db = load()
    material = next(iter(db))
    assert db.get(material.name.lower()) is material


def test_missing_material_raises_with_count():
    db = load()
    with pytest.raises(KeyError, match="не найден"):
        db.get("нет-такого")


def test_gaps_report_lists_missing_parameters():
    db = load()
    gaps = db.gaps()
    assert gaps, "у пустых карточек обязаны быть пробелы"
    assert any("dew_point_margin_k" in g for g in gaps)


def test_readiness_of_empty_card(empty_card):
    r = empty_card.readiness()
    assert not r.usable_on_site
    assert r.verified_share == 0.0
    assert "application.dew_point_margin_k" in r.missing_required
    assert "нет ссылки на TDS" in r.summary()


def test_readiness_of_complete_card(pu_membrane):
    r = pu_membrane.readiness()
    assert r.usable_on_site
    assert not r.missing_required
    assert r.counts[Status.VERIFIED] >= 5


def test_roles_parsed_as_enum():
    db = load()
    for material in db:
        assert all(isinstance(role, Role) for role in material.roles)
