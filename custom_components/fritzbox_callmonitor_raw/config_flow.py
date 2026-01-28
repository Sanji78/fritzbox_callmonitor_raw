from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME

from homeassistant.config_entries import ConfigEntry, OptionsFlow
from .options_flow import FritzboxCallmonitorRawOptionsFlowHandler

from .const import (
    CONF_PHONEBOOK_ID,
    CONF_PREFIXES,
    CONF_TR064_PORT,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_TR064_PORT,
    DOMAIN,
)


class FritzboxCallmonitorRawConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return FritzboxCallmonitorRawOptionsFlowHandler(config_entry)
        
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional("callmonitor_port", default=DEFAULT_PORT): vol.Coerce(int),
                    vol.Optional(CONF_TR064_PORT, default=DEFAULT_TR064_PORT): vol.Coerce(int),
                    vol.Required(CONF_USERNAME, default="admin"): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_PHONEBOOK_ID, default=0): vol.Coerce(int),
                    vol.Optional(CONF_PREFIXES, default=""): str,
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                }
            )
            return self.async_show_form(step_id="user", data_schema=schema, errors={})

        host: str = user_input[CONF_HOST]
        callmonitor_port: int = user_input["callmonitor_port"]
        tr064_port: int = user_input[CONF_TR064_PORT]
        username: str = user_input[CONF_USERNAME]
        password: str = user_input[CONF_PASSWORD]
        phonebook_id: int = user_input[CONF_PHONEBOOK_ID]
        prefixes_raw: str = user_input.get(CONF_PREFIXES, "")
        name: str = user_input.get(CONF_NAME, DEFAULT_NAME)

        prefixes = [p.strip() for p in prefixes_raw.split(",") if p.strip()]

        await self.async_set_unique_id(f"{host}:{callmonitor_port}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=name,
            data={
                CONF_HOST: host,
                "callmonitor_port": callmonitor_port,
                CONF_TR064_PORT: tr064_port,
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
                CONF_PHONEBOOK_ID: phonebook_id,
                CONF_PREFIXES: prefixes,
                CONF_NAME: name,
            },
        )