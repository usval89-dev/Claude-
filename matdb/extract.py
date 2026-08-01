"""Извлечение параметров из текста TDS.

Модуль намеренно не знает про PDF: на вход подаётся список страниц как текст,
на выход — кандидаты с номером страницы и точной цитатой. Разбор файлов живёт
в ``tools/extract_tds.py``.

Устройство подчинено одному требованию: извлечение не имеет права молча
ошибиться. Поэтому

* каждый кандидат несёт цитату из документа — человек сверяет за секунды,
  не перечитывая TDS;
* два разных значения для одного поля дают конфликт, а не победу первого;
* поле без кандидатов остаётся пробелом, а не заполняется догадкой;
* всё извлечённое получает статус ``tds``, но никогда ``verified``.

Правила настроены на точность, а не на полноту: пропущенный параметр стоит
пяти минут ручной работы, ошибочно извлечённый — протечки.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterator

from .values import Status, Value

#: Число в европейском или английском формате: 1.5, 1,5, +5, -10.
NUM = r"[-+]?\d+(?:[.,]\d+)?"

#: Разделители диапазона: дефис, тире, «to», «до», многоточие.
RANGE_SEP = r"(?:\s*(?:-|–|—|\.\.\.|…|to|до|and|и)\s*)"

#: Обозначения градуса Цельсия во всех написаниях, которые встречаются в TDS.
DEG_C = r"(?:°|º|o|°)?\s*[CС]"

#: Промежуток между ключевым словом и числом — без цифр и без конца предложения.
#:
#: Ограничение принципиальное, а не косметическое. С обычным ``[^.\n]`` правило
#: «N °C выше точки росы» на фразе «between +5°C and +35°C and at least 3°C above
#: the dew point» захватывает первое число диапазона и выдаёт запас 5 K вместо
#: 3 K. Ошибка выглядит совершенно правдоподобно и не обнаруживается глазом при
#: просмотре карточки. Запрет цифр в промежутке означает: число берётся то,
#: которое действительно относится к ключевому слову, а не первое подходящее.
GAP = r"[^.\n\d]"


def _num(raw: str) -> float:
    """Разобрать число, приняв запятую как десятичный разделитель."""
    return float(raw.replace(",", ".").replace("+", ""))


def _tidy(text: str) -> str:
    """Схлопнуть переносы и лишние пробелы, сохранив содержание."""
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class Candidate:
    """Одно найденное значение вместе с доказательством."""

    field: str
    value: float
    unit: str
    page: int
    quote: str
    rule: str

    def __str__(self) -> str:
        return f"{self.field} = {self.value} {self.unit} (с. {self.page}, правило {self.rule})"


@dataclass(frozen=True)
class Rule:
    """Правило извлечения: регулярное выражение плюс разбор совпадения."""

    name: str
    pattern: re.Pattern[str]
    handler: Callable[[re.Match[str]], list[tuple[str, float, str]]]
    note: str = ""

    def apply(self, text: str, page: int) -> Iterator[Candidate]:
        for m in self.pattern.finditer(text):
            quote = _tidy(m.group(0))
            for fname, value, unit in self.handler(m):
                yield Candidate(
                    field=fname, value=value, unit=unit, page=page, quote=quote, rule=self.name
                )


def _range(lo_field: str, hi_field: str, unit: str):
    def handler(m: re.Match[str]) -> list[tuple[str, float, str]]:
        return [
            (lo_field, _num(m.group("lo")), unit),
            (hi_field, _num(m.group("hi")), unit),
        ]

    return handler


def _single(fname: str, unit: str, group: str = "v"):
    def handler(m: re.Match[str]) -> list[tuple[str, float, str]]:
        return [(fname, _num(m.group(group)), unit)]

    return handler


def _rx(p: str) -> re.Pattern[str]:
    return re.compile(p, re.IGNORECASE | re.UNICODE)


# --- правила ---------------------------------------------------------------
#
# Область действия («основание» / «воздух») определяется словом в самом
# документе. Формулировку «application temperature» без уточнения нельзя
# разложить на два параметра, поэтому она попадает в отдельное поле, которое
# человек разносит руками.

RULES: list[Rule] = [
    # Температура основания, явно названная.
    Rule(
        "substrate_temp_range_en",
        _rx(
            rf"(?:substrate|surface)\s+temperature{GAP}{{0,40}}?"
            rf"(?P<lo>{NUM})\s*{DEG_C}?{RANGE_SEP}(?P<hi>{NUM})\s*{DEG_C}"
        ),
        _range("application.substrate_temp_min_c", "application.substrate_temp_max_c", "°C"),
    ),
    Rule(
        "substrate_temp_range_ru",
        _rx(
            rf"температур\w*\s+основани\w+{GAP}{{0,40}}?от\s*(?P<lo>{NUM})\s*{DEG_C}?"
            rf"\s*до\s*(?P<hi>{NUM})\s*{DEG_C}"
        ),
        _range("application.substrate_temp_min_c", "application.substrate_temp_max_c", "°C"),
    ),
    # Температура воздуха, явно названная.
    Rule(
        "ambient_temp_range_en",
        _rx(
            rf"(?:ambient|air)\s+temperature{GAP}{{0,40}}?"
            rf"(?P<lo>{NUM})\s*{DEG_C}?{RANGE_SEP}(?P<hi>{NUM})\s*{DEG_C}"
        ),
        _range("application.ambient_temp_min_c", "application.ambient_temp_max_c", "°C"),
    ),
    Rule(
        "ambient_temp_range_ru",
        _rx(
            rf"температур\w*\s+(?:воздуха|окружающ\w+\s+среды){GAP}{{0,40}}?от\s*(?P<lo>{NUM})"
            rf"\s*{DEG_C}?\s*до\s*(?P<hi>{NUM})\s*{DEG_C}"
        ),
        _range("application.ambient_temp_min_c", "application.ambient_temp_max_c", "°C"),
    ),
    # Температура нанесения без указания, воздух это или основание.
    Rule(
        "application_temp_range_unscoped_en",
        _rx(
            rf"application\s+temperature{GAP}{{0,30}}?"
            rf"(?P<lo>{NUM})\s*{DEG_C}?{RANGE_SEP}(?P<hi>{NUM})\s*{DEG_C}"
        ),
        _range("_unscoped.temp_min_c", "_unscoped.temp_max_c", "°C"),
        note="документ не разделяет воздух и основание — разнести вручную",
    ),
    Rule(
        "application_temp_range_unscoped_ru",
        _rx(
            rf"температур\w*\s+нанесени\w+{GAP}{{0,30}}?от\s*(?P<lo>{NUM})\s*{DEG_C}?"
            rf"\s*до\s*(?P<hi>{NUM})\s*{DEG_C}"
        ),
        _range("_unscoped.temp_min_c", "_unscoped.temp_max_c", "°C"),
        note="документ не разделяет воздух и основание — разнести вручную",
    ),
    # Запас над точкой росы.
    Rule(
        "dew_point_margin_en",
        _rx(rf"(?P<v>{NUM})\s*(?:°|º)?\s*[CK]{GAP}{{0,40}}?above\s+the\s+dew\s*[- ]?point"),
        _single("application.dew_point_margin_k", "K"),
    ),
    Rule(
        "dew_point_margin_ru",
        _rx(rf"на\s*(?P<v>{NUM})\s*(?:°|º)?\s*[CСK]?{GAP}{{0,30}}?выше\s+точки\s+росы"),
        _single("application.dew_point_margin_k", "K"),
    ),
    # Предельная влажность воздуха.
    Rule(
        "ambient_rh_max_en",
        _rx(
            rf"relative\s+humidity{GAP}{{0,40}}?(?:below|less\s+than|lower\s+than|max\w*|"
            rf"not\s+exceed\w*|<|≤)\s*(?P<v>{NUM})\s*%"
        ),
        _single("application.ambient_rh_max_percent", "%"),
    ),
    Rule(
        "ambient_rh_max_ru",
        _rx(
            rf"относительн\w+\s+влажност\w+{GAP}{{0,40}}?(?:не\s+более|не\s+выше|ниже|менее|<|≤)"
            rf"\s*(?P<v>{NUM})\s*%"
        ),
        _single("application.ambient_rh_max_percent", "%"),
    ),
    # Предельная влажность основания. Метод замера ищется отдельно.
    Rule(
        "substrate_moisture_max_en",
        _rx(
            rf"moisture\s*(?:content|level)?{GAP}{{0,50}}?(?:below|less\s+than|lower\s+than|"
            rf"max\w*|not\s+exceed\w*|<|≤)\s*(?P<v>{NUM})\s*%"
        ),
        _single("application.substrate_moisture_max_percent", "%"),
    ),
    Rule(
        "substrate_moisture_max_ru",
        _rx(
            rf"влажност\w+\s+основани\w+{GAP}{{0,40}}?(?:не\s+более|не\s+выше|ниже|менее|<|≤)"
            rf"\s*(?P<v>{NUM})\s*%"
        ),
        _single("application.substrate_moisture_max_percent", "%"),
    ),
    # Межслойный интервал.
    Rule(
        "overcoat_range_en",
        _rx(
            rf"(?:recoat\w*|overcoat\w*|next\s+(?:layer|coat)|second\s+(?:layer|coat))"
            rf"{GAP}{{0,60}}?(?P<lo>{NUM}){RANGE_SEP}(?P<hi>{NUM})\s*(?:hours?|hrs?|h)\b"
        ),
        _range("cure.overcoat_min_h", "cure.overcoat_max_h", "ч"),
    ),
    Rule(
        "overcoat_range_ru",
        _rx(
            rf"(?:следующ\w+\s+сло\w+|второй\s+сло\w+|межслойн\w+)"
            rf"{GAP}{{0,60}}?(?P<lo>{NUM}){RANGE_SEP}(?P<hi>{NUM})\s*(?:часов?|часа|ч)\b"
        ),
        _range("cure.overcoat_min_h", "cure.overcoat_max_h", "ч"),
    ),
    # Опорная температура, при которой приведены времена.
    Rule(
        "reference_temp_en",
        _rx(
            rf"(?:times?|values?|data|figures?){GAP}{{0,60}}?at\s*(?P<v>{NUM})\s*{DEG_C}"
            rf"|at\s*(?P<v2>{NUM})\s*{DEG_C}{GAP}{{0,40}}?(?:and\s*\d+\s*%\s*)?"
            rf"relative\s+humidity"
        ),
        lambda m: [
            (
                "cure.reference_temp_c",
                _num(m.group("v") or m.group("v2")),
                "°C",
            )
        ],
    ),
    Rule(
        "reference_temp_ru",
        _rx(rf"(?:значени\w+|времен\w+|данн\w+){GAP}{{0,60}}?при\s*(?P<v>{NUM})\s*{DEG_C}"),
        _single("cure.reference_temp_c", "°C"),
    ),
    # Расход. Диапазон и одиночное значение разведены, чтобы не склеить их.
    Rule(
        "consumption_range",
        _rx(
            rf"(?:consumption|расход){GAP}{{0,60}}?(?P<lo>{NUM}){RANGE_SEP}(?P<hi>{NUM})"
            rf"\s*(?:kg|кг)\s*/\s*(?:m|м)\s*[²2]"
        ),
        _range("_consumption.min_kg_m2", "_consumption.max_kg_m2", "кг/м²"),
        note="диапазон: уточнить, это расход на слой или суммарный по системе",
    ),
    Rule(
        "consumption_single",
        _rx(
            rf"(?:consumption|расход){GAP}{{0,60}}?(?P<v>{NUM})\s*(?:kg|кг)\s*/\s*(?:m|м)\s*[²2]"
        ),
        _single("_consumption.value_kg_m2", "кг/м²"),
        note="уточнить, это расход на слой или суммарный по системе",
    ),
]

#: Признаки метода замера влажности основания. Число без метода бессмысленно:
#: 4 % по CM и 4 % весовым методом — разные состояния бетона.
MOISTURE_METHOD_MARKERS = {
    "CM-метод": _rx(r"\bCM[-\s]?(?:method|метод|измерител)|карбидн"),
    "весовой метод": _rx(r"\b(?:by\s+weight|gravimetric|весов\w+|по\s+массе)"),
    "относительная влажность в толще": _rx(
        r"(?:in-situ|equilibrium)\s+relative\s+humidity|относительн\w+\s+влажност\w+\s+в\s+толще"
    ),
}

#: Поля, без которых карточка не отвечает на вопрос «можно ли наносить».
REQUIRED = (
    "application.substrate_temp_min_c",
    "application.substrate_temp_max_c",
    "application.dew_point_margin_k",
    "application.substrate_moisture_max_percent",
    "application.ambient_rh_max_percent",
)


@dataclass
class Extraction:
    """Результат разбора документа."""

    source_id: str
    """Основа ссылки на источник, например ``isomat/isoflex-pu-500@2024-03``."""
    candidates: list[Candidate] = field(default_factory=list)
    moisture_methods: list[tuple[str, int]] = field(default_factory=list)
    pages: int = 0
    notes: list[str] = field(default_factory=list)

    def by_field(self) -> dict[str, list[Candidate]]:
        out: dict[str, list[Candidate]] = {}
        for c in self.candidates:
            out.setdefault(c.field, []).append(c)
        return out

    def resolved(self) -> dict[str, Candidate]:
        """Поля, где все кандидаты сошлись на одном значении."""
        return {
            fname: cands[0]
            for fname, cands in self.by_field().items()
            if len({c.value for c in cands}) == 1 and not fname.startswith("_")
        }

    def conflicts(self) -> dict[str, list[Candidate]]:
        """Поля с расхождением: в карточку не попадают, решает человек."""
        return {
            fname: cands
            for fname, cands in self.by_field().items()
            if len({c.value for c in cands}) > 1
        }

    def unscoped(self) -> dict[str, list[Candidate]]:
        """Найденное, но не разложенное по полям автоматически."""
        return {f: c for f, c in self.by_field().items() if f.startswith("_")}

    def gaps(self) -> list[str]:
        found = set(self.resolved())
        return [f for f in REQUIRED if f not in found]

    def to_card(self, card: dict) -> dict:
        """Дописать в карточку однозначно найденные значения.

        Существующие поля не затираются: ручная правка человека главнее
        машинного разбора.
        """
        out = {**card}
        for fname, cand in sorted(self.resolved().items()):
            block, _, leaf = fname.partition(".")
            section = dict(out.get(block) or {})
            if leaf in section:
                continue
            value = Value(
                cand.value,
                unit=cand.unit,
                status=Status.TDS,
                source=f"tds:{self.source_id}#p{cand.page}",
                note=self._note_for(leaf, cand),
            )
            section[leaf] = value.to_json()
            out[block] = section
        return out

    def _note_for(self, leaf: str, cand: Candidate) -> str:
        if leaf == "substrate_moisture_max_percent":
            if self.moisture_methods:
                methods = ", ".join(sorted({m for m, _ in self.moisture_methods}))
                return f"метод по документу: {methods}; сверить привязку к числу"
            return "МЕТОД ЗАМЕРА В ДОКУМЕНТЕ НЕ НАЙДЕН — число непригодно без него"
        return f"цитата: {cand.quote}"

    def report(self) -> str:
        """Отчёт для сверки с документом: цитата на каждое число."""
        lines = [
            f"Документ: {self.source_id}, страниц: {self.pages}",
            f"Найдено значений: {len(self.resolved())}, "
            f"конфликтов: {len(self.conflicts())}, пробелов: {len(self.gaps())}",
            "",
        ]
        if self.resolved():
            lines.append("ИЗВЛЕЧЕНО (статус tds — требует сверки человеком):")
            for fname, c in sorted(self.resolved().items()):
                lines.append(f"  {fname} = {c.value} {c.unit}   с. {c.page}")
                lines.append(f"      «{c.quote}»")
            lines.append("")
        if self.conflicts():
            lines.append("КОНФЛИКТЫ — в карточку не записаны, выбирает человек:")
            for fname, cands in sorted(self.conflicts().items()):
                values = ", ".join(str(c.value) for c in cands)
                lines.append(f"  {fname}: {values}")
                for c in cands:
                    lines.append(f"      с. {c.page}: «{c.quote}»")
            lines.append("")
        if self.unscoped():
            lines.append("НЕ РАЗЛОЖЕНО ПО ПОЛЯМ — разнести вручную:")
            for fname, cands in sorted(self.unscoped().items()):
                for c in cands:
                    lines.append(f"  {fname} = {c.value} {c.unit}  с. {c.page}")
                    lines.append(f"      «{c.quote}»")
            lines.append("")
        if self.moisture_methods:
            methods = ", ".join(f"{m} (с. {p})" for m, p in self.moisture_methods)
            lines.append(f"Метод замера влажности основания: {methods}")
        else:
            lines.append(
                "Метод замера влажности основания в документе не найден — "
                "предел влажности без метода применять нельзя."
            )
        lines.append("")
        if self.gaps():
            lines.append("НЕ НАЙДЕНО (остаётся пробелом, догадки не подставляются):")
            for f in self.gaps():
                lines.append(f"  {f}")
        else:
            lines.append("Все ключевые поля найдены.")
        for n in self.notes:
            lines.append(f"Примечание: {n}")
        lines.append("")
        lines.append(
            "Ни одно значение не получает статус verified автоматически. "
            "Сверьте цитаты с документом и проставьте verified_by/verified_at."
        )
        return "\n".join(lines)


def extract(pages: list[str], source_id: str) -> Extraction:
    """Разобрать документ, поданный как список текстов страниц."""
    result = Extraction(source_id=source_id, pages=len(pages))
    seen_notes: set[str] = set()
    for i, raw in enumerate(pages, start=1):
        text = _tidy(raw)
        for rule in RULES:
            for cand in rule.apply(text, i):
                result.candidates.append(cand)
                if rule.note and rule.note not in seen_notes:
                    seen_notes.add(rule.note)
                    result.notes.append(f"{rule.name}: {rule.note}")
        for method, pattern in MOISTURE_METHOD_MARKERS.items():
            if pattern.search(text):
                result.moisture_methods.append((method, i))
    return result
