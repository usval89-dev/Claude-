"""Проверка движка совместимости, включая его поведение при незнании."""

from __future__ import annotations

from matdb.compat import Compat, CompatibilityIndex, Rule
from matdb.loader import load
from matdb.models import CoatingSystem, Family, Role, SystemLayer
from matdb.values import Status


def test_unknown_pair_is_not_compatible():
    """Главное свойство движка: молчание базы не означает «можно»."""
    index = CompatibilityIndex()
    res = index.resolve(Family.PU_1K_MOISTURE, Family.SILICONE)
    assert res.verdict is Compat.UNKNOWN
    assert res.verdict.blocking
    assert "не означает" in res.rationale


def test_direction_matters():
    db = load()
    pu_over_bitumen = db.compatibility.resolve(Family.PU_1K_MOISTURE, Family.BITUMEN)
    bitumen_over_pu = db.compatibility.resolve(Family.BITUMEN, Family.PU_1K_MOISTURE)
    assert pu_over_bitumen.verdict is not bitumen_over_pu.verdict


def test_product_rule_beats_family_rule(pu_membrane):
    index = CompatibilityIndex()
    index.add(
        Rule(
            over="family:pu_1k_moisture",
            under="family:bitumen",
            verdict=Compat.NEEDS_PRIMER,
            rationale="общее правило семейства",
        )
    )
    index.add(
        Rule(
            over=f"product:{pu_membrane.id}",
            under="family:bitumen",
            verdict=Compat.INCOMPATIBLE,
            rationale="частное правило продукта",
            status=Status.VERIFIED,
            source="tds:fixture",
        )
    )
    res = index.resolve(pu_membrane, Family.BITUMEN)
    assert res.verdict is Compat.INCOMPATIBLE
    assert res.rationale == "частное правило продукта"


def test_family_rule_applies_to_product_of_that_family(pu_membrane):
    db = load()
    res = db.compatibility.resolve(pu_membrane, Family.SILICONE)
    assert res.verdict is Compat.INCOMPATIBLE
    assert res.matched_rule == "family:pu_1k_moisture → family:silicone"


def test_silicone_blocks_everything_above_it():
    db = load()
    for over in (Family.PU_1K_MOISTURE, Family.EPOXY_2K):
        assert db.compatibility.resolve(over, Family.SILICONE).verdict is Compat.INCOMPATIBLE


def test_hydrophobic_impregnation_blocks_coatings():
    db = load()
    res = db.compatibility.resolve(Family.PU_1K_MOISTURE, Family.SILANE_SILOXANE)
    assert res.verdict is Compat.INCOMPATIBLE


def test_pmma_dissolves_polyurethane_beneath():
    db = load()
    assert (
        db.compatibility.resolve(Family.PMMA, Family.PU_1K_MOISTURE).verdict
        is Compat.INCOMPATIBLE
    )
    # А в обратную сторону — вопрос подготовки поверхности, а не химии.
    assert (
        db.compatibility.resolve(Family.PU_1K_MOISTURE, Family.PMMA).verdict
        is Compat.CONDITIONAL
    )


def test_needs_primer_names_the_primer_family():
    db = load()
    res = db.compatibility.resolve(Family.PU_1K_MOISTURE, Family.BITUMEN)
    assert res.verdict is Compat.NEEDS_PRIMER
    assert Family.EPOXY_2K in res.primer_families
    assert res.conditions


def test_render_marks_unverified_basis():
    db = load()
    text = db.compatibility.resolve(Family.PU_1K_MOISTURE, Family.BITUMEN).render()
    assert "основание вывода: reference" in text


def test_system_check_walks_every_joint(pu_membrane, empty_card):
    system = CoatingSystem(
        name="тест",
        substrate="бетон",
        layers=[
            SystemLayer(material=empty_card, role=Role.PRIMER),
            SystemLayer(material=pu_membrane, role=Role.MEMBRANE),
        ],
    )
    db = load()
    results = db.compatibility.check_system(system)
    assert len(results) == 1
    # ПУ по эпоксидному праймеру — штатная связка с условиями.
    assert results[0].verdict is Compat.CONDITIONAL


def test_worst_verdict_dominates():
    db = load()
    res = [
        db.compatibility.resolve(Family.PU_1K_MOISTURE, Family.CEMENTITIOUS),
        db.compatibility.resolve(Family.PU_1K_MOISTURE, Family.SILICONE),
    ]
    assert CompatibilityIndex.worst(res) is Compat.INCOMPATIBLE


def test_worst_of_empty_is_compatible():
    assert CompatibilityIndex.worst([]) is Compat.COMPATIBLE
