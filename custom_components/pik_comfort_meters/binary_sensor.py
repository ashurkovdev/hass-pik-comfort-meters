"""Бинарные сенсоры для мониторинга ошибок интеграции PIK Comfort Meters."""

import logging
from datetime import datetime
from typing import Optional

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo, DeviceRegistry
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

    # Создаём "gateway" устройство для мониторинга
    device_registry = await _get_monitoring_device(hass, entry)

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_monitoring")},
        name="PIK Comfort Meters Monitoring",
        manufacturer="PIK Comfort",
        model="Integration Monitor",
        sw_version="1.0",
        configuration_url="https://pik-comfort.ru",
    )

    update_name = "Update Error"
    submit_name = "Submit Error"
    entities = [
        PIKErrorBinarySensor(
            coordinator=coordinator,
            error_tracker=error_tracker,
            error_key=BINARY_SENSOR_UPDATE_ERROR,
            name=update_name,
            device_info=device_info,
            device_class=BinarySensorDeviceClass.PROBLEM,
        ),
        PIKErrorBinarySensor(
            coordinator=coordinator,
            error_tracker=error_tracker,
            error_key=BINARY_SENSOR_SUBMIT_ERROR,
            name=submit_name,
            device_info=device_info,
            device_class=BinarySensorDeviceClass.PROBLEM,
        ),
    ]
    async_add_entities(entities, True)


async def _get_monitoring_device(hass: HomeAssistant, entry: ConfigEntry) -> DeviceRegistry:
    """Создаёт или получает устройство мониторинга интеграции."""
    from homeassistant.helpers import device_registry as dr
    device_registry = dr.async_get(hass)
    device_unique_id = f"{entry.entry_id}_monitoring"
    device_name = "PIK Comfort Meters Monitoring"

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device_unique_id)},
        name=device_name,
        manufacturer="PIK Comfort",
        model="Integration Monitor",
        sw_version="1.0",
        configuration_url="https://pik-comfort.ru",
    )
    return device_registry


class PIKErrorBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Бинарный сенсор для мониторинга ошибок интеграции."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(
        self,
        coordinator: CoordinatorEntity,
        error_tracker: dict,
        error_key: str,
        name: str,
        device_info: DeviceInfo,
        device_class: BinarySensorDeviceClass,
    ):
        super().__init__(coordinator)
        self._error_key = error_key
        self._attr_name = f"PIK Comfort {name}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{error_key}"
        self._error_tracker = error_tracker
        self._attr_device_info = device_info
        self._attr_device_class = device_class
        self._attr_is_on = False

    @property
    def is_on(self) -> bool:
        """Возвращает True если есть ошибка."""
        return self._error_tracker.get(self._error_key, {}).get("error", False)

    @property
    def extra_state_attributes(self) -> dict:
        """Возвращает дополнительные атрибуты."""
        data = self._error_tracker.get(self._error_key, {})
        attrs = {
            "last_attempt": data.get("last_attempt"),
            "last_success": data.get("last_success"),
        }
        # Добавляем сообщение об ошибке, если есть
        if "last_error_message" in data and data["last_error_message"]:
            attrs["last_error_message"] = data["last_error_message"]
        return attrs

    @property
    def available(self) -> bool:
        """Возвращает True если последняя попытка была успешной."""
        return self._error_tracker.get(self._error_key, {}).get("last_success") is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()