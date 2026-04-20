"""Config flow для PIK Comfort Meters."""

import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import (
    DOMAIN,
    CONF_PHONE,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    MAX_UPDATE_INTERVAL,
)
from .const import CONF_ACCOUNT_UID, CONF_TOKEN
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
    VERSION = 1

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        _LOGGER.debug("Starting config flow async_step_user, input provided: %s", bool(user_input))
        errors = {}
        if user_input is not None:
            session = aiohttp_client.async_get_clientsession(self.hass)
            api = PIKComfortAPI(session, user_input[CONF_PHONE], user_input[CONF_PASSWORD])
            try:
                authenticated = await api.authenticate()
                if not authenticated:
                    errors["base"] = "auth_failed"
                else:
                    await api.get_dashboard()
                    if api.account_uid:
                        return self.async_create_entry(
                            title=f"PIK Comfort ({user_input[CONF_PHONE]})",
                            data={
                                CONF_PHONE: user_input[CONF_PHONE],
                                CONF_PASSWORD: user_input[CONF_PASSWORD],
                                CONF_UPDATE_INTERVAL: user_input[CONF_UPDATE_INTERVAL],
                                CONF_ACCOUNT_UID: api.account_uid,
                                CONF_TOKEN: api.token,
                            },
                        )
                    else:
                        errors["base"] = "no_accounts"
            except Exception as err:  # catch unexpected errors and log them
                _LOGGER.exception("Unexpected error during PIK Comfort authentication: %s", err)
                errors["base"] = "unknown"
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        _LOGGER.debug("Providing options flow for config entry %s", getattr(config_entry, 'entry_id', None))
        return PIKComfortOptionsFlow(config_entry)


class PIKComfortOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=self.config_entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Clamp(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL)),
                }
            ),
        )