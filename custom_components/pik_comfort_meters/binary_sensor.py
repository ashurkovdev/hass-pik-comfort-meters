"""Бинарные сенсоры для мониторинга ошибок интеграции PIK Comfort Meters."""

import logging
from datetime import datetime
from typing import Optional

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, BINARY_SENSOR_UPDATE_ERROR, BINARY_SENSOR_SUBMIT_ERROR

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Настройка бинарных сенсоров."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    error_tracker = hass.data[DOMAIN][entry.entry_id]["error_tracker"]

    update_name = "Update Error"
    submit_name = "Submit Error"
    entities = [
        PIKErrorBinarySensor(coordinator, error_tracker, BINARY_SENSOR_UPDATE_ERROR, update_name),
        PIKErrorBinarySensor(coordinator, error_tracker, BINARY_SENSOR_SUBMIT_ERROR, submit_name),
    ]
    async_add_entities(entities, True)


class PIKErrorBinarySensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator, error_tracker, error_key: str, name: str):
        super().__init__(coordinator)
        self._error_key = error_key
        self._attr_name = f"PIK Comfort {name}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{error_key}"
        self._error_tracker = error_tracker
        self._attr_is_on = False

    @property
    def is_on(self):
        return self._error_tracker.get(self._error_key, {}).get("error", False)

    @property
    def extra_state_attributes(self):
        data = self._error_tracker.get(self._error_key, {})
        attrs = {
            "last_attempt": data.get("last_attempt"),
            "last_success": data.get("last_success"),
        }
        # Добавляем сообщение об ошибке, если есть
        if "last_error_message" in data and data["last_error_message"]:
            attrs["last_error_message"] = data["last_error_message"]
        return attrs

    @callback
    def _handle_coordinator_update(self):
        self.async_write_ha_state()