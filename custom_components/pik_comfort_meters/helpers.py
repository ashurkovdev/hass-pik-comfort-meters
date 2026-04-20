"""Translation helper utilities for the integration.

This module provides a tiny, optimized accessor and an async refresher
that other modules should use instead of duplicating translation logic.

API:
- `translate(hass, key, section='common', **fmt)` -> str
    Synchronous accessor that reads cached translations from
    `hass.data[DOMAIN]['translations']` and returns a formatted string.

- `async_refresh_translations(hass)` -> coroutine
    Async function that fetches translations from Home Assistant and
    writes them to `hass.data[DOMAIN]['translations']`.

Design notes:
- The accessor is intentionally tiny and pure-sync so it can be used
  from entity properties and in synchronous contexts.
- Call `async_refresh_translations` at setup and when HA language
  changes to keep the cache fresh.
"""
from typing import Any

from homeassistant.helpers import translation as ha_translation

from .const import DOMAIN


async def async_refresh_translations(hass) -> None:
    """Fetch translations from Home Assistant and cache them.

    This should be awaited from async setup code or scheduled as a task.
    """
    try:
        translations = await ha_translation.async_get_translations(hass, DOMAIN)
    except Exception:
        translations = {}
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["translations"] = translations


def translate(hass, key: str, section: str = "common", **fmt: Any) -> str:
    """Return translated string for `key` from cached translations.

    - `section` selects where to look: "common", "errors", "binary", "config".
    - Function is synchronous and safe to call from entity properties.
    - If translation is not found, returns `key` or formatted `key.format(...)`.
    """
    translations = hass.data.get(DOMAIN, {}).get("translations", {})
    lang = getattr(getattr(hass, "config", None), "language", None) or "en"
    t = translations.get(lang) or translations.get("en") or {}

    try:
        # Preferred location for generic/utility strings is under services.<domain>.strings
        svc_strings = t.get("services", {}).get(DOMAIN, {}).get("strings", {})
        if section == "common":
            val = svc_strings.get(key) or t.get("entity", {}).get("sensor", {}).get("pik_comfort_meters", {}).get(key)
        elif section == "binary":
            val = svc_strings.get(key) or t.get("entity", {}).get("binary_sensor", {}).get("pik_comfort_meters", {}).get(key)
        elif section == "errors":
            svc = t.get("services", {}).get(DOMAIN, {}).get("submit_reading", {})
            fields = svc.get("fields", {}) if isinstance(svc, dict) else {}
            field_key = f"error_{key}"
            val = fields.get(field_key)
            if isinstance(val, dict):
                val = val.get("description") or val.get("name")
        elif section == "config":
            val = t.get("config", {}).get("error", {}).get(key)
        else:
            val = None

        if val:
            return val.format(**fmt) if fmt else val
    except Exception:
        pass

    return (fmt and key.format(**fmt)) or key
