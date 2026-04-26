"""Инициализация интеграции PIK Comfort Meters."""

import logging
import asyncio
from datetime import datetime
from typing import List, Union

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import aiohttp_client, device_registry as dr, entity_registry as er
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, BINARY_SENSOR_SUBMIT_ERROR
from .api import PIKComfortAPI

_LOGGER = logging.getLogger(__name__)

# No custom translation helper imported; English literals are used inline.


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Настройка интеграции."""
    hass.data.setdefault(DOMAIN, {})
    if entry.entry_id not in hass.data[DOMAIN]:
        hass.data[DOMAIN][entry.entry_id] = {}

    # No custom translation preloading — use plain English strings in-place.

    # Регистрация сервиса submit_reading
    async def handle_submit(call: ServiceCall):
        """Отправка показаний для устройства по device_id."""
        device_id = call.data.get("device_id")
        if not device_id:
            raise HomeAssistantError("Missing parameter: device_id")

        # Получаем устройство из реестра
        device_registry = dr.async_get(hass)
        device = device_registry.async_get(device_id)
        if not device:
            raise HomeAssistantError(f"Device {device_id} not found")

        # Находим все сенсоры, принадлежащие этому устройству
        entity_registry = er.async_get(hass)
        sensor_entities = []
        for entity in entity_registry.entities.values():
            if entity.device_id == device_id and entity.domain == "sensor" and entity.platform == DOMAIN:
                sensor_entities.append(entity.entity_id)

        if not sensor_entities:
            raise HomeAssistantError(f"No sensors found for device {device_id}")

        # Сортируем по tariff_type (атрибут), безопасно обрабатываем None states
        # Фильтруем только сенсоры с типом "accounted" для отправки показаний
        readings = []
        sensor_data = []
        for entity_id in sensor_entities:
            state = hass.states.get(entity_id)
            if state:
                sensor_type = state.attributes.get("sensor_type") if state.attributes else None
                # Используем только сенсоры типа "accounted" для отправки показаний
                if sensor_type == "accounted":
                    tariff_type = state.attributes.get("tariff_type", 0) if state.attributes else 0
                    sensor_data.append((tariff_type, entity_id, state))
        
        for tariff_type, entity_id, state in sorted(sensor_data, key=lambda x: x[0]):
            if state.state not in (None, "unknown", "unavailable"):
                readings.append(float(state.state))

        if not readings:
            raise HomeAssistantError(f"No valid readings for device {device_id}")

        # Получаем meter_id из сохранённых метаданных устройства
        # device.identifiers is a set of tuples like {(domain, unique_id)}
        device_unique_id = next(iter(device.identifiers))[1]  # (DOMAIN, unique_id)
        device_meta = hass.data[DOMAIN][entry.entry_id].get("devices", {}).get(device_unique_id)
        if not device_meta:
            raise HomeAssistantError(f"Device metadata not found for {device_unique_id}")
        meter_id = device_meta["meter_id"]

        # Отправляем показания
        api = hass.data[DOMAIN][entry.entry_id]["api"]
        error_tracker = hass.data[DOMAIN][entry.entry_id].get("error_tracker", {})
        submit_tracker = error_tracker.get(BINARY_SENSOR_SUBMIT_ERROR, {})
        submit_tracker["last_attempt"] = datetime.now().isoformat()
        coordinator = hass.data[DOMAIN][entry.entry_id].get("coordinator")
        try:
            readings_to_send = readings[0] if len(readings) == 1 else readings
            success = await api.submit_readings(meter_id, readings_to_send)
            if success:
                submit_tracker["error"] = False
                submit_tracker["last_success"] = datetime.now().isoformat()
                submit_tracker["last_error_message"] = None
                if coordinator:
                    coordinator.async_update_listeners()
            else:
                error_msg = "API returned failure (unknown reason)"
                submit_tracker["error"] = True
                submit_tracker["last_error_message"] = error_msg
                if coordinator:
                    coordinator.async_update_listeners()
                raise HomeAssistantError(error_msg)
        except Exception as e:
            error_msg = str(e)
            submit_tracker["error"] = True
            submit_tracker["last_error_message"] = error_msg
            if coordinator:
                coordinator.async_update_listeners()
                raise HomeAssistantError(f"Failed to submit readings: {error_msg}")

    hass.services.async_register(DOMAIN, "submit_reading", handle_submit)

    # No listener for core config updates since no dynamic translations are used.

    # Загружаем платформы
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "binary_sensor"])

    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    unload_ok = unload_ok and await hass.config_entries.async_forward_entry_unload(entry, "binary_sensor")
    if unload_ok:
        hass.services.async_remove(DOMAIN, "submit_reading")
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok