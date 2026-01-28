from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_PHONEBOOK_ID, CONF_PREFIXES, CONF_TR064_PORT, DEFAULT_TR064_PORT


class FritzboxCallmonitorRawOptionsFlowHandler(OptionsFlow):
    """Handle options for FRITZ!Box CallMonitor (Raw + TR-064)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is None:
            prefixes_list = self._entry.options.get(
                CONF_PREFIXES, self._entry.data.get(CONF_PREFIXES, [])
            )
            prefixes_str = ", ".join(prefixes_list) if isinstance(prefixes_list, list) else ""

            schema = vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=self._entry.options.get(
                            CONF_USERNAME, self._entry.data.get(CONF_USERNAME, "admin")
                        ),
                    ): str,
                    vol.Required(
                        CONF_PASSWORD,
                        default=self._entry.options.get(
                            CONF_PASSWORD, self._entry.data.get(CONF_PASSWORD, "")
                        ),
                    ): str,
                    vol.Required(
                        CONF_TR064_PORT,
                        default=self._entry.options.get(
                            CONF_TR064_PORT,
                            self._entry.data.get(CONF_TR064_PORT, DEFAULT_TR064_PORT),
                        ),
                    ): vol.Coerce(int),
                    vol.Required(
                        CONF_PHONEBOOK_ID,
                        default=self._entry.options.get(
                            CONF_PHONEBOOK_ID, self._entry.data.get(CONF_PHONEBOOK_ID, 0)
                        ),
                    ): vol.Coerce(int),
                    vol.Optional(CONF_PREFIXES, default=prefixes_str): str,
                }
            )
            return self.async_show_form(step_id="init", data_schema=schema)

        prefixes_raw = user_input.get(CONF_PREFIXES, "")
        prefixes = [p.strip() for p in prefixes_raw.split(",") if p.strip()]

        return self.async_create_entry(
            title="",
            data={
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_TR064_PORT: user_input[CONF_TR064_PORT],
                CONF_PHONEBOOK_ID: user_input[CONF_PHONEBOOK_ID],
                CONF_PREFIXES: prefixes,
            },
        )