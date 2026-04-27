"""Сенсоры для показаний счетчиков ПИК Комфорт."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers import device_registry as dr

from .const import (
    DOMAIN,
    RESOURCE_TYPES,
    UNIT_MAPPING,
    DEVICE_CLASS_MAPPING,
    BINARY_SENSOR_UPDATE_ERROR,
    SENSOR_TYPE_ACCOUNTED,
    SENSOR_TYPE_SUBMITTED,
    SENSOR_TYPE_CONSUMPTION,
    SENSOR_TYPE_UPDATED,
    SENSOR_TYPE_CREATED,
)
from .api import PIKComfortAPI

_LOGGER = logging.getLogger(__name__)


def _get_tariff_suffix(tariff_count: int, tariff_type: int) -> str:
    """Возвращает суффикс для unique_id в зависимости от количества тарифов."""
    return "" if tariff_count == 1 else f"_t{tariff_type}"


def _get_display_suffix(tariff_count: int, tariff_type: int) -> str:
    """Возвращает суффикс для имени в зависимости от количества тарифов."""
    if tariff_count == 1:
        return ""
    if tariff_type == 1:
        return " (Day)"
    elif tariff_type == 2:
        return " (Night)"
    elif tariff_type == 3:
        return " (Morning & Evening)"
    else:
        return f" Tariff {tariff_type}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Настройка сенсоров и устройств."""
    # Получаем координатор из hass.data (создан в __init__.py)
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    _LOGGER.info("Using shared coordinator for sensors: %d meters", len(coordinator.data) if coordinator.data else 0)
    if coordinator.data:
        for m in coordinator.data:
            _LOGGER.info("Meter: factory_number=%s, _uid=%s, resource_type=%s, tariffs=%s",
                        m.get("factory_number"), m.get("_uid"), m.get("resource_type"), m.get("tariffs"))

    # Регистрация устройств и сенсоров
    device_registry = dr.async_get(hass)
    entities = []

    for meter in coordinator.data or []:
        factory_number = meter.get("factory_number")
        meter_id = meter.get("_uid")
        resource_type = meter.get("resource_type")
        resource_key = RESOURCE_TYPES.get(resource_type, "unknown")
        device_name = f"PIK meter: {resource_key} ({factory_number})"
        device_unique_id = f"{entry.entry_id}_{factory_number}"

        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, device_unique_id)},
            name=device_name,
            manufacturer="PIK Comfort",
            model=resource_key,
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
        _LOGGER.info("Meter %s has %d tariffs: %s", meter.get("factory_number"), tariff_count, tariffs)

        # Создаем device_info для всех сенсоров этого счетчика
        device_info = DeviceInfo(
            identifiers={(DOMAIN, device_unique_id)},
            name=device_name,
            manufacturer="PIK Comfort",
            model=resource_key,
            sw_version="1.0",
            configuration_url="https://pik-comfort.ru",
        )

        for tariff in tariffs:
            tariff_type = tariff.get("type")
            tariff_suffix = _get_tariff_suffix(tariff_count, tariff_type)
            display_suffix = _get_display_suffix(tariff_count, tariff_type)

            # 1. Сенсор учтенных показаний (accounted)
            entities.append(PIKMeterSensor(
                coordinator=coordinator,
                meter=meter,
                tariff_type=tariff_type,
                sensor_type=SENSOR_TYPE_ACCOUNTED,
                unique_id=f"pik_comfort_meters{factory_number}_accounted{tariff_suffix}",
                name=f"{device_name}{display_suffix} Accounted",
                device_info=device_info,
            ))

            # 2. Сенсор переданных показаний (submitted)
            entities.append(PIKMeterSensor(
                coordinator=coordinator,
                meter=meter,
                tariff_type=tariff_type,
                sensor_type=SENSOR_TYPE_SUBMITTED,
                unique_id=f"pik_comfort_meters{factory_number}_submitted{tariff_suffix}",
                name=f"{device_name}{display_suffix} Submitted",
                device_info=device_info,
            ))

            # 3. Сенсор потребления за месяц (consumption)
            entities.append(PIKMeterSensor(
                coordinator=coordinator,
                meter=meter,
                tariff_type=tariff_type,
                sensor_type=SENSOR_TYPE_CONSUMPTION,
                unique_id=f"pik_comfort_meters{factory_number}_consumption{tariff_suffix}",
                name=f"{device_name}{display_suffix} Monthly Consumption",
                device_info=device_info,
            ))

            # 4. Сенсор даты обновления показаний (timestamp)
            entities.append(PIKMeterTimestampSensor(
                coordinator=coordinator,
                meter=meter,
                tariff_type=tariff_type,
                sensor_type=SENSOR_TYPE_UPDATED,
                unique_id=f"pik_comfort_meters{factory_number}_updated{tariff_suffix}",
                name=f"{device_name}{display_suffix} Last Updated",
                device_info=device_info,
            ))

            # 5. Сенсор даты создания показаний (timestamp)
            entities.append(PIKMeterTimestampSensor(
                coordinator=coordinator,
                meter=meter,
                tariff_type=tariff_type,
                sensor_type=SENSOR_TYPE_CREATED,
                unique_id=f"pik_comfort_meters{factory_number}_created{tariff_suffix}",
                name=f"{device_name}{display_suffix} Created",
                device_info=device_info,
            ))

    if len(entities) == 0:
        _LOGGER.warning("No meters found. Check your PIK account.")

    async_add_entities(entities, True)

    _LOGGER.info(
        "Created %d sensor entities for %d meters", len(entities), len(coordinator.data) if coordinator.data else 0
    )


class PIKMetersCoordinator(DataUpdateCoordinator):
    """Координатор для обновления данных счетчиков."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: PIKComfortAPI,
        update_interval_sec: int,
        error_tracker: dict,
        config_entry: ConfigEntry,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval_sec),
            config_entry=config_entry,
        )
        self.api = api
        self.error_tracker = error_tracker

    async def _async_update_data(self) -> List[Dict[str, Any]]:
        self.error_tracker[BINARY_SENSOR_UPDATE_ERROR]["last_attempt"] = datetime.now().isoformat()
        try:
            meters = await self.api.get_account_meters()
            if meters is None:
                raise UpdateFailed("Failed to get account meters")
            self.error_tracker[BINARY_SENSOR_UPDATE_ERROR]["error"] = False
            self.error_tracker[BINARY_SENSOR_UPDATE_ERROR]["last_success"] = datetime.now().isoformat()
            self.error_tracker[BINARY_SENSOR_UPDATE_ERROR]["last_error_message"] = None
            self.async_update_listeners()
            return meters
        except Exception as err:
            self.error_tracker[BINARY_SENSOR_UPDATE_ERROR]["error"] = True
            self.error_tracker[BINARY_SENSOR_UPDATE_ERROR]["last_error_message"] = str(err)
            self.async_update_listeners()
            raise UpdateFailed(f"Update error: {err}") from err


class PIKMeterSensor(CoordinatorEntity, SensorEntity):
    """Сенсор для показаний счётчика (учтенные, переданные, потребление)."""

    def __init__(
        self,
        coordinator,
        meter: Dict[str, Any],
        tariff_type: int,
        sensor_type: str,
        unique_id: str,
        name: str,
        device_info: DeviceInfo,
    ):
        super().__init__(coordinator)
        self._meter = meter
        self._tariff_type = tariff_type
        self._sensor_type = sensor_type
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_device_info = device_info

        resource_type = meter.get("resource_type")
        self._attr_unit_of_measurement = UNIT_MAPPING.get(resource_type, "kWh")
        self._attr_device_class = DEVICE_CLASS_MAPPING.get(resource_type)
        
        _LOGGER.debug(
            "Sensor %s: resource_type=%s, unit=%s, device_class=%s",
            self._attr_unique_id, resource_type, self._attr_unit_of_measurement, self._attr_device_class
        )

        self._state: Optional[float] = None

        # Округление до 3 знаков после запятой для сенсоров показаний и потребления
        if self._sensor_type in (SENSOR_TYPE_ACCOUNTED, SENSOR_TYPE_SUBMITTED, SENSOR_TYPE_CONSUMPTION):
            self._attr_suggested_display_precision = 3

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return {"tariff_type": self._tariff_type, "sensor_type": self._sensor_type}

    @callback
    def _handle_coordinator_update(self):
        meters = self.coordinator.data
        if not meters:
            _LOGGER.debug("No meters data available for sensor %s", self._attr_unique_id)
            return
        for meter in meters:
            if meter.get("_uid") == self._meter.get("_uid"):
                for tariff in meter.get("tariffs", []):
                    if tariff.get("type") == self._tariff_type:
                        accounted = tariff.get("value")
                        submitted = tariff.get("user_value")
                        average = tariff.get("average_in_month")

                        # Устанавливаем значение в зависимости от типа сенсора
                        if self._sensor_type == SENSOR_TYPE_ACCOUNTED:
                            self._state = accounted
                        elif self._sensor_type == SENSOR_TYPE_SUBMITTED:
                            self._state = submitted
                        elif self._sensor_type == SENSOR_TYPE_CONSUMPTION:
                            self._state = average

                        _LOGGER.debug(
                            "Sensor %s (type=%s) updated: value=%s, accounted=%s, submitted=%s, average=%s",
                            self._attr_unique_id, self._sensor_type, self._state, accounted, submitted, average
                        )
                        break
                break
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._handle_coordinator_update()


class PIKMeterTimestampSensor(CoordinatorEntity, SensorEntity):
    """Сенсор для дат (дата обновления, дата создания)."""

    def __init__(
        self,
        coordinator,
        meter: Dict[str, Any],
        tariff_type: int,
        sensor_type: str,
        unique_id: str,
        name: str,
        device_info: DeviceInfo,
    ):
        super().__init__(coordinator)
        self._meter = meter
        self._tariff_type = tariff_type
        self._sensor_type = sensor_type
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_device_info = device_info

        # Для timestamp сенсоров используем device_class timestamp
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

        self._state: Optional[datetime] = None

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return {"tariff_type": self._tariff_type, "sensor_type": self._sensor_type}

    @callback
    def _handle_coordinator_update(self):
        meters = self.coordinator.data
        if not meters:
            _LOGGER.debug("No meters data available for timestamp sensor %s", self._attr_unique_id)
            return
        for meter in meters:
            if meter.get("_uid") == self._meter.get("_uid"):
                for tariff in meter.get("tariffs", []):
                    if tariff.get("type") == self._tariff_type:
                        user_updated = tariff.get("user_value_updated")
                        user_created = tariff.get("user_value_created")

                        # Устанавливаем значение в зависимости от типа сенсора
                        if self._sensor_type == SENSOR_TYPE_UPDATED:
                            if user_updated:
                                try:
                                    parsed_dt = datetime.fromisoformat(user_updated.replace('Z', '+00:00'))
                                    # Добавляем UTC timezone, если его нет
                                    if parsed_dt.tzinfo is None:
                                        parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
                                    self._state = parsed_dt
                                except (ValueError, AttributeError):
                                    self._state = None
                            else:
                                self._state = None
                        elif self._sensor_type == SENSOR_TYPE_CREATED:
                            if user_created:
                                try:
                                    parsed_dt = datetime.fromisoformat(user_created.replace('Z', '+00:00'))
                                    # Добавляем UTC timezone, если его нет
                                    if parsed_dt.tzinfo is None:
                                        parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
                                    self._state = parsed_dt
                                except (ValueError, AttributeError):
                                    self._state = None
                            else:
                                self._state = None

                        _LOGGER.debug(
                            "Timestamp sensor %s (type=%s) updated: user_updated=%s, user_created=%s, state=%s",
                            self._attr_unique_id, self._sensor_type, user_updated, user_created, self._state
                        )
                        break
                break
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._handle_coordinator_update()