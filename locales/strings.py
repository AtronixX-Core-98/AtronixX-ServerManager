"""strings.py - translations (Persian default / English) and the t() helper

t(key, lang, **kw): values in kw are HTML-escaped automatically unless wrapped in Raw(...).
The token %BRAND% in any string is replaced by the configured display name (BOT_NAME).
"""

from __future__ import annotations

import html
import logging

from config import settings
from locales._admin import ADMIN
from locales._user import USER

logger = logging.getLogger("servermanager.i18n")

_BRAND = html.escape(settings.brand, quote=False)


def _brand(pair: tuple[str, str]) -> tuple[str, str]:
    return pair[0].replace("%BRAND%", _BRAND), pair[1].replace("%BRAND%", _BRAND)


S: dict[str, tuple[str, str]] = {k: _brand(v) for k, v in {**USER, **ADMIN}.items()}


class Raw(str):
    """Ready-made HTML that must not be escaped again."""


def t(key: str, lang: str = "fa", **kw) -> str:
    entry = S.get(key)
    if entry is None:
        logger.error("missing string key: %s", key)
        return key
    text = entry[0] if lang == "fa" else entry[1]
    if not kw:
        return text
    safe = {k: (v if isinstance(v, Raw) else html.escape(str(v), quote=False)) for k, v in kw.items()}
    try:
        return text.format(**safe)
    except (KeyError, IndexError, ValueError):
        logger.exception("bad placeholders for %s", key)
        return text
