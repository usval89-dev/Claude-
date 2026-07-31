"""База материалов для гидроизоляции и наливных покрытий.

Проект решает три задачи:

1. Расчёт условий нанесения — точка росы, запас над ней, влажность у поверхности,
   пересчёт времён отверждения на фактическую температуру (``psychro``,
   ``application``).
2. Хранение параметров продуктов вместе с происхождением каждого числа
   (``values``, ``models``, ``loader``).
3. Проверка совместимости слоёв в системе (``compat``).

Правило, на котором держится всё остальное: значение без указания источника и
статуса достоверности в базу не попадает.
"""

from .application import Severity, check_application, cure_schedule
from .compat import Compat, CompatibilityIndex, Rule
from .loader import Database, DataError, load
from .models import CoatingSystem, CureMode, Family, Material, Role, SystemLayer
from .psychro import dew_point, measure, surface_rh
from .values import Status, Value, unknown

__all__ = [
    "Severity",
    "check_application",
    "cure_schedule",
    "Compat",
    "CompatibilityIndex",
    "Rule",
    "Database",
    "DataError",
    "load",
    "CoatingSystem",
    "CureMode",
    "Family",
    "Material",
    "Role",
    "SystemLayer",
    "dew_point",
    "measure",
    "surface_rh",
    "Status",
    "Value",
    "unknown",
]
