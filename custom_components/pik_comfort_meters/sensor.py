"""Сенсоры для показаний счетчиков ПИК Комфорт."""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers import aiohttp_client, device_registry as dr

from .const import (
    DOMAIN,
    CONF_PHONE,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    CONF_ACCOUNT_UID,
    CONF_TOKEN,
    RESOURCE_TYPES,
    RESOURCE_NAMES,
    UNIT_MAPPING,
    BINARY_SENSOR_UPDATE_ERROR,
)
from .api import PIKComfortAPI
from .helpers import translate


# Use the centralized `translate` helper from `helpers.py`

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Настройка сенсоров и устройств."""
    phone = entry.data[CONF_PHONE]
    password = entry.data[CONF_PASSWORD]
    interval = entry.data.get(CONF_UPDATE_INTERVAL)

    session = aiohttp_client.async_get_clientsession(hass)
    api = PIKComfortAPI(session, phone, password)
    api.token = entry.data.get(CONF_TOKEN)
    api.account_uid = entry.data.get(CONF_ACCOUNT_UID)

    if not api.token or not api.account_uid:
        if not await api.authenticate():
            raise UpdateFailed(translate(hass, "auth_failed_update", section="errors"))
        await api.get_dashboard()

    # Трекер ошибок
    error_tracker = {
        BINARY_SENSOR_UPDATE_ERROR: {"error": False, "last_attempt": None, "last_success": None, "last_error_message": None},
        "submit_error": {"error": False, "last_attempt": None, "last_success": None, "last_error_message": None},
    }

    coordinator = PIKMetersCoordinator(hass, api, interval, error_tracker)
    # expose config_entry on coordinator so other platforms can access entry_id
    coordinator.config_entry = entry
    await coordinator.async_config_entry_first_refresh()

    # Регистрация устройств и сенсоров
    device_registry = dr.async_get(hass)
    entities = []

    for meter in coordinator.data:
        factory_number = meter.get("factory_number")
        meter_id = meter.get("_uid")
        resource_type = meter.get("resource_type")
        resource_key = RESOURCE_TYPES.get(resource_type, "unknown")
        device_name = f"PIK {RESOURCE_NAMES.get(resource_type)} {factory_number}"
        device_unique_id = f"{entry.entry_id}_{factory_number}"

        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, device_unique_id)},
            name=device_name,
            manufacturer="PIK Comfort",
            model=RESOURCE_NAMES.get(resource_type),
            sw_version="1.0",
            configuration_url="https://pik-comfort.ru",
        )

        # Сохраняем метаданные устройства
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN].setdefault(entry.entry_id, {})
        hass.data[DOMAIN][entry.entry_id].setdefault("devices", {})[device_unique_id] = {
            "meter_id": meter_id,
            "factory_number": factory_number,
            "resource_type": resource_type,
            "device_id": device.id,
        }

        # Создаём сенсоры для каждого тарифа
        tariffs = meter.get("tariffs", [])
        tariff_count = len(tariffs)
        for tariff in tariffs:
            tariff_type = tariff.get("type")
            # Unique ID rules:
            # - If meter has only 1 tariff, omit _t<tariff_type> suffix
            # - Otherwise include _t<tariff_type>
            if tariff_count == 1:
                sensor_unique_id = f"pik_comfort_meters_{factory_number}"
            else:
                sensor_unique_id = f"pik_comfort_meters_{factory_number}_t{tariff_type}"

            # Display name rules:
            # - If only 1 tariff, do not append tariff text
            # - If 2 tariffs: tariff 1 -> (День), tariff 2 -> (Ночь)
            # - If 3 tariffs: tariff 1 -> (День), tariff 2 -> (Ночь), tariff 3 -> Утро и вечер
            if tariff_count == 1:
                sensor_name = device_name
            else:
                # Localized display names for tariffs
                if tariff_type == 1:
                    display = translate(hass, "tariff_day", section="common")
                elif tariff_type == 2:
                    display = translate(hass, "tariff_night", section="common")
                elif tariff_type == 3:
                    display = translate(hass, "tariff_morning_evening", section="common")
                else:
                    tpl = translate(hass, "tariff_generic", section="common")
                    display = tpl.format(num=tariff_type)
                sensor_name = f"{device_name} {display}"

            entity = PIKMeterSensor(
                coordinator=coordinator,
                meter=meter,
                tariff_type=tariff_type,
                unique_id=sensor_unique_id,
                name=sensor_name,
                device_id=device.id,
                device_unique_id=device_unique_id,
            )
            entities.append(entity)

    async_add_entities(entities, True)

    # Сохраняем координатор и API для других компонентов
    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator
    hass.data[DOMAIN][entry.entry_id]["api"] = api
    hass.data[DOMAIN][entry.entry_id]["error_tracker"] = error_tracker


class PIKMetersCoordinator(DataUpdateCoordinator):
    """Координатор для обновления данных счетчиков."""

    def __init__(self, hass: HomeAssistant, api: PIKComfortAPI, update_interval_sec: int, error_tracker: dict):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval_sec),
        )
        self.api = api
        self.error_tracker = error_tracker

    async def _async_update_data(self) -> List[Dict[str, Any]]:
        self.error_tracker[BINARY_SENSOR_UPDATE_ERROR]["last_attempt"] = datetime.now().isoformat()
        try:
            meters = await self.api.get_account_meters()
            if meters is None:
                raise UpdateFailed(translate(self.hass, "fetch_meters_failed", section="errors"))
            self.error_tracker[BINARY_SENSOR_UPDATE_ERROR]["error"] = False
            self.error_tracker[BINARY_SENSOR_UPDATE_ERROR]["last_success"] = datetime.now().isoformat()
            self.error_tracker[BINARY_SENSOR_UPDATE_ERROR]["last_error_message"] = None
            self.async_update_listeners()
            return meters
        except Exception as err:
            self.error_tracker[BINARY_SENSOR_UPDATE_ERROR]["error"] = True
            self.error_tracker[BINARY_SENSOR_UPDATE_ERROR]["last_error_message"] = str(err)
            self.async_update_listeners()
            raise UpdateFailed(translate(self.hass, "update_failed", section="errors", err=str(err))) from err


class PIKMeterSensor(CoordinatorEntity, SensorEntity):
    """Сенсор для одного тарифа счётчика."""

    def __init__(self, coordinator, meter: Dict[str, Any], tariff_type: int, unique_id: str, name: str, device_id: str, device_unique_id: str):
        super().__init__(coordinator)
        self._meter = meter
        self._tariff_type = tariff_type
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_device_id = device_id
        self._device_unique_id = device_unique_id
        resource_type = meter.get("resource_type")
        self._attr_unit_of_measurement = UNIT_MAPPING.get(resource_type)
        self._attr_device_class = "water" if resource_type in (1, 2) else "energy" if resource_type == 3 else None
        self._state = None
        self._attrs = {}

    @property
    def native_value(self):
        return self._state

    @property
    def device_info(self):
        # Return device identifiers using the unique id created when the device was registered
        return {"identifiers": {(DOMAIN, self._device_unique_id)}}

    @property
    def extra_state_attributes(self):
        data = {"tariff_type": self._tariff_type}
        # Merge in any collected attributes from the latest coordinator update
        data.update(self._attrs or {})
        return data

    @callback
    def _handle_coordinator_update(self):
        meters = self.coordinator.data
        for meter in meters:
            if meter.get("_uid") == self._meter.get("_uid"):
                for tariff in meter.get("tariffs", []):
                    if tariff.get("type") == self._tariff_type:
                        # Primary sensor value: 'value' from API is considered 'accounted' (учтенные)
                        accounted = tariff.get("value")
                        submitted = tariff.get("user_value")
                        average = tariff.get("average_in_month")
                        user_updated = tariff.get("user_value_updated")
                        user_created = tariff.get("user_value_created")

                        self._state = accounted

                        # Prepare extra attributes to expose both accounted and submitted readings
                        va_label = translate(self.hass, "value_accounted_label", section="common")
                        vs_label = translate(self.hass, "value_submitted_label", section="common")
                        avg_label = translate(self.hass, "average_in_month_label", section="common")
                        self._attrs = {
                            "value_accounted": accounted,
                            "value_accounted_label": va_label,
                            "value_submitted": submitted,
                            "value_submitted_label": vs_label,
                            "average_in_month": average,
                            "average_in_month_label": avg_label,
                            "user_value_updated": user_updated,
                            "user_value_created": user_created,
                        }
                        break
                break
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_coordinator_update))
        self._handle_coordinator_update()