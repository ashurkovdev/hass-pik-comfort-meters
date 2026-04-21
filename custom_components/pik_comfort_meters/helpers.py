"""Translation helper utilities for the integration.

This module provides a tiny, optimized accessor and an async refresher
that other modules should use instead of duplicating translation logic.
"""
from typing import Any

from homeassistant.helpers import translation as ha_translation

from .const import DOMAIN
import json
from pathlib import Path

async def async_refresh_translations(hass) -> None:
    """Fetch official translations + load custom extra strings."""
    # 1. Получаем стандартные переводы HA
    try:
        official = await ha_translation.async_get_translations(hass, DOMAIN)
    except Exception:
        official = {}

    # 2. Загружаем кастомные строки из extra_{lang}.json
    lang = hass.config.language if hasattr(hass.config, 'language') else 'en'
    extra = {}
    try:
        extra_path = Path(__file__).parent / "translations" / f"extra_{lang}.json"
        if extra_path.exists():
            with open(extra_path, encoding="utf-8") as f:
                extra = json.load(f)
    except Exception:
        pass

    # 3. Объединяем: кастомные строки добавляем в корень под специальным ключом
    combined = official.get(lang, {})
    combined["_extra"] = extra   # сохраняем под ключом _extra

    # 4. Сохраняем в hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["translations"] = {lang: combined}


def translate(hass, key: str, section: str = "common", **fmt: Any) -> str:
    """Return translated string from official or extra translations."""
    translations = hass.data.get(DOMAIN, {}).get("translations", {})
    lang = getattr(getattr(hass, "config", None), "language", None) or "en"
    t = translations.get(lang) or {}

    val = None
    # Сначала ищем в официальных секциях
    if section == "common":
        svc = t.get("services", {}).get(DOMAIN, {}).get("submit_reading", {})
        val = svc.get(key) or t.get("entity", {}).get("sensor", {}).get("pik_comfort_meters", {}).get(key)
    elif section == "binary":
        val = t.get("entity", {}).get("binary_sensor", {}).get("pik_comfort_meters", {}).get(key)
    elif section == "errors":
        svc = t.get("services", {}).get(DOMAIN, {}).get("submit_reading", {})
        fields = svc.get("fields", {})
        field_key = f"error_{key}"
        val = fields.get(field_key, {}).get("description")
    elif section == "config":
        val = t.get("config", {}).get("error", {}).get(key)

    # Если не нашли, ищем в extra-словаре
    if val is None:
        extra = t.get("_extra", {})
        val = extra.get(key)

    if val:
        return val.format(**fmt) if fmt else val
    return (fmt and key.format(**fmt)) or key