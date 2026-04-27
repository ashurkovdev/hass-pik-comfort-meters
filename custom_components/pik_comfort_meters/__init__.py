"""Инициализация интеграции PIK Comfort Meters."""

import logging
import asyncio
from datetime import datetime
from typing import List, Union, Dict, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import aiohttp_client, device_registry as dr, entity_registry as er
from homeassistant.exceptions import HomeAssistantError, ConfigEntryNotReady

from .const import DOMAIN, BINARY_SENSOR_SUBMIT_ERROR, BINARY_SENSOR_UPDATE_ERROR, CONF_TOKEN, CONF_ACCOUNT_UID, CONF_UPDATE_INTERVAL
from .api import PIKComfortAPI
from .sensor import PIKMetersCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Настройка интеграции."""
    hass.data.setdefault(DOMAIN, {})
    if entry.entry_id not in hass.data[DOMAIN]:
        hass.data[DOMAIN][entry.entry_id] = {}

    # Проверяем и обновляем токен при необходимости
    api = await _initialize_api(hass, entry)
    if not api:
        _LOGGER.error("Failed to initialize API for entry %s", entry.entry_id)
        return False

    hass.data[DOMAIN][entry.entry_id]["api"] = api

    # Создаём единый координатор
    interval = entry.data.get(CONF_UPDATE_INTERVAL, 21600)
    error_tracker = {
        BINARY_SENSOR_SUBMIT_ERROR: {
            "error": False,
            "last_attempt": None,
            "last_success": None,
            "last_error_message": None,
        },
        BINARY_SENSOR_UPDATE_ERROR: {
            "error": False,
            "last_attempt": None,
            "last_success": None,
            "last_error_message": None,
        },
    }

    coordinator = PIKMetersCoordinator(hass, api, interval, error_tracker, entry)

    # Первая попытка загрузки данных
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Failed to load data for %s: %s", entry.entry_id, err)
        raise ConfigEntryNotReady(f"Initial data fetch failed: {err}") from err

    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator
    hass.data[DOMAIN][entry.entry_id]["error_tracker"] = error_tracker

    # Регистрация сервиса submit_reading
    async def handle_submit(call: ServiceCall):
        """Отправка показаний для устройства по device_id."""
        # device_id comes from fields with device selector (returns string)
        device_id = call.data.get("device_id")
        if not device_id:
            raise HomeAssistantError("Missing parameter: device_id")

        # Получаем устройство из реестра
        device_registry = dr.async_get(hass)
        device = device_registry.async_get(device_id)
        if not device:
            raise HomeAssistantError(f"Device {device_id} not found")

        # Проверяем, переданы ли показания явно
        readings = None
        if "readings" in call.data:
            readings_data = call.data.get("readings")
            if isinstance(readings_data, (int, float)):
                readings = [float(readings_data)]
            elif isinstance(readings_data, list):
                readings = [float(r) for r in readings_data]
            else:
                raise HomeAssistantError(f"Invalid readings format: {type(readings_data)}")
            if not readings:
                raise HomeAssistantError("Empty readings provided")

        # Если показания не переданы, берем текущие значения сенсоров
        if readings is None:
            # Находим все сенсоры, принадлежащие этому устройству
            entity_registry = er.async_get(hass)
            sensor_entities = []
            for entity in entity_registry.entities.values():
                if (
                    entity.device_id == device_id
                    and entity.domain == "sensor"
                    and entity.platform == DOMAIN
                ):
                    sensor_entities.append(entity.entity_id)

            if not sensor_entities:
                raise HomeAssistantError(f"No sensors found for device {device_id}")

            # Сортируем по tariff_type (атрибут), безопасно обрабатываем None states
            # Фильтруем только сенсоры типа "accounted" для отправки показаний
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
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        try:
            readings_to_send = readings[0] if len(readings) == 1 else readings
            success = await api.submit_readings(meter_id, readings_to_send)
            if success:
                submit_tracker["error"] = False
                submit_tracker["last_success"] = datetime.now().isoformat()
                submit_tracker["last_error_message"] = None
                # Немедленно обновляем данные после успешной отправки показаний
                await coordinator.async_request_refresh()
            else:
                error_msg = "API returned failure (unknown reason)"
                submit_tracker["error"] = True
                submit_tracker["last_error_message"] = error_msg
                raise HomeAssistantError(error_msg)
        except HomeAssistantError:
            raise
        except Exception as e:
            error_msg = str(e)
            submit_tracker["error"] = True
            submit_tracker["last_error_message"] = error_msg
            coordinator.async_update_listeners()
            raise HomeAssistantError(f"Failed to submit readings: {error_msg}")

    hass.services.async_register(DOMAIN, "submit_reading", handle_submit)

    # Загружаем платформы
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "binary_sensor"])

    entry.async_on_unload(entry.add_update_listener(async_update_options))
    _LOGGER.info("PIK Comfort Meters integration loaded successfully for entry %s", entry.entry_id)
    return True


async def _initialize_api(hass: HomeAssistant, entry: ConfigEntry) -> PIKComfortAPI:
    """Инициализация API клиента с проверкой токена."""
    phone = entry.data.get("phone")
    password = entry.data.get("password")
    token = entry.data.get(CONF_TOKEN)
    account_uid = entry.data.get(CONF_ACCOUNT_UID)

    if not phone or not password:
        _LOGGER.error("Missing phone or password in config entry")
        return None

    session = aiohttp_client.async_get_clientsession(hass)
    api = PIKComfortAPI(session, phone, password)

    # Если есть сохранённый токен и account_uid, пробуем использовать их
    if token and account_uid:
        api.token = token
        api.account_uid = account_uid

        # Проверяем валидность токена
        try:
            meters = await api.get_account_meters()
            if meters is not None:
                _LOGGER.debug("Token is still valid for phone %s", phone)
                return api
        except Exception as e:
            _LOGGER.warning("Token validation failed, will re-authenticate: %s", e)

        # Токен недействителен, пробуем переаутентифицироваться
        _LOGGER.warning("Token expired for phone %s, re-authenticating...", phone)
        api.token = None
        api.account_uid = None

    # Аутентификация с нуля
    if not await api.authenticate():
        _LOGGER.error("Authentication failed for phone %s", phone)
        return None

    await api.get_dashboard()
    if not api.account_uid:
        _LOGGER.error("No account found for phone %s", phone)
        return None

    _LOGGER.debug("Authentication successful for phone %s, account_uid: %s", phone, api.account_uid)
    return api


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Обновление опций интеграции."""
    try:
        # При изменении интервала обновления просто перезагружаем интеграцию
        await hass.config_entries.async_reload(entry.entry_id)
    except Exception as e:
        _LOGGER.error("Error updating options for entry %s: %s", entry.entry_id, e)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Выгрузка интеграции."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    unload_ok = unload_ok and await hass.config_entries.async_forward_entry_unload(entry, "binary_sensor")
    if unload_ok:
        hass.services.async_remove(DOMAIN, "submit_reading")
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok