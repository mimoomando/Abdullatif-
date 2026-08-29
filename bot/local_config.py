"""
قراءة الإعدادات المحلية — ما لا يجوز أن يدخل المستودع أبدًا.

    مسار الطرفية · رقم الحساب · كلمة السر · توكن تيليجرام · chat_id

تُقرأ من `config.local.py` بجذر المشروع، وهو ممنوع في `.gitignore`.
والقالب `config.local.example.py` مرفوع **بلا قيم** ليُنسَخ ويُملأ.

⚠️ **لا تُطبع القيم الحسّاسة أبدًا** — لا في خطأ ولا في سجل ولا في
رسالة تيليجرام. رسالة خطأ تحمل كلمة سرّ تُسرَّب في مكانين معًا.
`describe()` يعرض ما وُجد وما نقص **بلا كشف قيمة**.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

CONFIG_FILENAME = "config.local.py"

# المفاتيح الحسّاسة — تُخفى في كل عرض
SECRET_KEYS = frozenset({
    "MT5_PASSWORD", "MT5_LOGIN", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID",
})

REQUIRED_FOR_BRIDGE = ("MT5_PATH",)
OPTIONAL_FOR_BRIDGE = ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER")


class ConfigMissing(RuntimeError):
    """الملف المحلي غير موجود أو ناقص."""


def project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def config_path() -> str:
    return os.path.join(project_root(), CONFIG_FILENAME)


def load(path: Optional[str] = None) -> Dict[str, Any]:
    """
    يحمّل الإعدادات المحلية كقاموس.

    يُرفع خطأ واضح إن غاب الملف — لا قيم افتراضية صامتة: بوت يتصل
    بحساب غير الذي تظنّه أسوأ من بوت لا يعمل.
    """
    target = path or config_path()
    if not os.path.exists(target):
        raise ConfigMissing(
            f"لا يوجد {CONFIG_FILENAME} في {project_root()}\n"
            f"انسخ القالب واملأه:\n"
            f"   copy config.local.example.py {CONFIG_FILENAME}\n"
            "وهو ممنوع في .gitignore فلن يُرفع."
        )

    spec = importlib.util.spec_from_file_location("config_local", target)
    if spec is None or spec.loader is None:
        raise ConfigMissing(f"تعذّرت قراءة {target}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return {k: v for k, v in vars(module).items() if k.isupper()}


def mt5_credentials(settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    يبني وسائط `initialize()` من الإعدادات.

    المسار وحده يكفي إن كانت الطرفية مسجَّلة الدخول أصلًا — وهو الحال
    الأشيع على جهاز يعمل دائمًا. ورقم الحساب وكلمة السر اختياريان.
    """
    missing = [k for k in REQUIRED_FOR_BRIDGE if not settings.get(k)]
    if missing:
        raise ConfigMissing(
            f"ينقص {CONFIG_FILENAME}: {' · '.join(missing)}\n"
            "MT5_PATH هو مسار terminal64.exe على جهازك."
        )

    out: Dict[str, Any] = {"path": settings["MT5_PATH"]}
    if settings.get("MT5_LOGIN"):
        out["login"] = int(settings["MT5_LOGIN"])
    if settings.get("MT5_PASSWORD"):
        out["password"] = settings["MT5_PASSWORD"]
    if settings.get("MT5_SERVER"):
        out["server"] = settings["MT5_SERVER"]
    return out


@dataclass(frozen=True)
class ConfigReport:
    present: List[str]
    missing: List[str]

    @property
    def ready(self) -> bool:
        return not self.missing

    def render(self) -> str:
        mark = "✅" if self.ready else "⚠️"
        L = [f"{mark} الإعدادات المحلية"]
        for k in self.present:
            hidden = " (محجوبة)" if k in SECRET_KEYS else ""
            L.append(f"   ✓ {k}{hidden}")
        for k in self.missing:
            L.append(f"   ✗ {k} — ناقص")
        return "\n".join(L)


def describe(settings: Dict[str, Any]) -> ConfigReport:
    """
    تقرير عمّا وُجد وما نقص — **بلا كشف أي قيمة**.

    القيم الحسّاسة تُعلَّم «محجوبة»: يكفيك أن تعرف أنها موجودة.
    """
    keys = list(REQUIRED_FOR_BRIDGE) + list(OPTIONAL_FOR_BRIDGE)
    present = [k for k in keys if settings.get(k)]
    missing = [k for k in REQUIRED_FOR_BRIDGE if not settings.get(k)]
    return ConfigReport(present=present, missing=missing)


def redact(settings: Dict[str, Any]) -> Dict[str, Any]:
    """نسخة صالحة للطباعة — القيم الحسّاسة مستبدَلة."""
    return {
        k: ("•••" if k in SECRET_KEYS and v else v)
        for k, v in settings.items()
    }
