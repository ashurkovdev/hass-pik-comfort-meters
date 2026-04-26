"""Config flow для PIK Comfort Meters."""

import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import (
    DOMAIN,
    CONF_PHONE,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    CONF_ACCOUNT_UID,
    CONF_TOKEN,
    DEFAULT_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    MAX_UPDATE_INTERVAL,
)
from .api import PIKComfortAPI

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PHONE): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
            vol.Coerce(int), vol.Clamp(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL)
        ),
    }
)


class PIKComfortConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow для PIK Comfort Meters."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Основной шаг конфигурации."""
        _LOGGER.debug("Starting config flow async_step_user, input provided: %s", bool(user_input))
        
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            phone = user_input[CONF_PHONE]
            password = user_input[CONF_PASSWORD]
            
            session = aiohttp_client.async_get_clientsession(self.hass)
            api = PIKComfortAPI(session, phone, password)
            
            try:
                authenticated = await api.authenticate()
                if not authenticated:
                    return self.async_abort(reason="auth_failed")
                
                await api.get_dashboard()
                
                if api.account_uid:
                    return self.async_create_entry(
                        title=f"PIK Comfort ({phone})",
                        data={
                            CONF_PHONE: phone,
                            CONF_PASSWORD: password,
                            CONF_UPDATE_INTERVAL: user_input[CONF_UPDATE_INTERVAL],
                            CONF_ACCOUNT_UID: api.account_uid,
                            CONF_TOKEN: api.token,
                        },
                    )
                else:
                    return self.async_abort(reason="no_accounts")
                    
            except Exception:
                _LOGGER.exception("Unexpected error during PIK Comfort authentication")
                return self.async_abort(reason="unknown")

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Возвращает options flow."""
        return PIKComfortOptionsFlow(config_entry)


class PIKComfortOptionsFlow(config_entries.OptionsFlow):
    """Options flow для PIK Comfort Meters."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Настройка опций."""
        if user_input is not None:
            # Если пароль был изменен, нужно переаутентифицироваться
            if CONF_PASSWORD in user_input and user_input[CONF_PASSWORD]:
                phone = self.config_entry.data.get(CONF_PHONE)
                password = user_input[CONF_PASSWORD]
                
                session = aiohttp_client.async_get_clientsession(self.hass)
                api = PIKComfortAPI(session, phone, password)
                
                try:
                    authenticated = await api.authenticate()
                    if not authenticated:
                        return self.async_abort(reason="auth_failed")
                    
                    await api.get_dashboard()
                    
                    if not api.account_uid:
                        return self.async_abort(reason="no_accounts")
                    
                    # Обновляем конфигурацию с новым паролем и токеном
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data={
                            **self.config_entry.data,
                            CONF_PASSWORD: password,
                            CONF_TOKEN: api.token,
                            CONF_ACCOUNT_UID: api.account_uid,
                        },
                    )
                    
                    # Если интервал не был изменен, добавляем его из текущих данных
                    if CONF_UPDATE_INTERVAL not in user_input:
                        user_input[CONF_UPDATE_INTERVAL] = self.config_entry.data.get(
                            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                        )
                    
                except Exception:
                    _LOGGER.exception("Unexpected error during password change")
                    return self.async_abort(reason="unknown")
            else:
                # Если пароль не менялся, просто обновляем интервал
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **self.config_entry.data,
                        CONF_UPDATE_INTERVAL: user_input.get(
                            CONF_UPDATE_INTERVAL,
                            self.config_entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                        ),
                    },
                )
            
            return self.async_create_entry(title="", data=user_input)

        # Формируем схему с текущими значениями
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=self.config_entry.data.get(
                        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                    ),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Clamp(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL),
                ),
                vol.Optional(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
