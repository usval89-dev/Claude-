"""Проверка слоя достоверности — он должен мешать, а не украшать."""

from __future__ import annotations

import datetime as dt

import pytest

from matdb.values import (
    Status,
    UnverifiedValueError,
    Value,
    audit,
    collect_gaps,
    unknown,
)


def test_unknown_cannot_carry_value():
    with pytest.raises(ValueError):
        Value(5, status=Status.UNKNOWN)


def test_known_status_requires_value():
    with pytest.raises(ValueError):
        Value(None, status=Status.TDS, source="tds:x@1")


def test_tds_value_requires_source():
    with pytest.raises(ValueError, match="источник"):
        Value(5, unit="°C", status=Status.TDS)


def test_verified_requires_a_person():
    with pytest.raises(ValueError, match="кто именно"):
        Value(5, unit="°C", status=Status.VERIFIED, source="tds:x@1")


def test_verified_value_is_trusted():
    v = Value(
        5,
        unit="°C",
        status=Status.VERIFIED,
        source="tds:x@1#p2",
        verified_by="прораб",
        verified_at=dt.date(2026, 7, 31),
    )
    assert v.trusted
    assert v.require_trusted("минимальная температура") == 5
    assert v.render() == "5 °C"


def test_tds_value_is_not_trusted_and_renders_with_marker():
    v = Value(5, unit="°C", status=Status.TDS, source="tds:x@1#p2")
    assert not v.trusted
    assert "[tds]" in v.render()
    with pytest.raises(UnverifiedValueError):
        v.require_trusted("минимальная температура")


def test_bare_number_is_rejected_on_load():
    # Молчаливое принятие голого числа уравняло бы его с проверенным.
    with pytest.raises(ValueError, match="без происхождения"):
        Value.from_json(5)


def test_json_roundtrip():
    v = Value(
        0.7,
        unit="кг/м²",
        status=Status.TDS,
        source="tds:x@2024-03#p3",
        note="второй слой",
    )
    assert Value.from_json(v.to_json()) == v


def test_null_becomes_explicit_unknown():
    assert Value.from_json(None).status is Status.UNKNOWN


def test_gaps_list_only_unknowns():
    values = {
        "a": Value(1, status=Status.TDS, source="s"),
        "b": unknown("°C", note="нет в TDS"),
        "c": unknown("%"),
    }
    gaps = collect_gaps("product-x", values)
    assert [g.field_name for g in gaps] == ["b", "c"]
    assert "нет в TDS" in str(gaps[0])


def test_audit_groups_by_status():
    values = {
        "a": Value(1, status=Status.TDS, source="s"),
        "b": unknown(),
        "c": Value(2, status=Status.REFERENCE),
    }
    result = audit("x", values)
    assert result == {"tds": ["a"], "reference": ["c"], "unknown": ["b"]}
