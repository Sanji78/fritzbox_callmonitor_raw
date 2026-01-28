from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from enum import StrEnum
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .callmonitor import FritzRawCallMonitorClient
from .const import (
    ATTR_ACCEPTED,
    ATTR_CLOSED,
    ATTR_DEVICE,
    ATTR_DURATION,
    ATTR_FROM,
    ATTR_FROM_NAME,
    ATTR_INITIATED,
    ATTR_PHONEBOOK_ENTRIES,
    ATTR_PHONEBOOK_LAST_REFRESH,
    ATTR_PHONEBOOK_STATUS,
    ATTR_PREFIXES,
    ATTR_RAW,
    ATTR_TO,
    ATTR_TO_NAME,
    ATTR_TYPE,
    ATTR_WITH,
    ATTR_WITH_NAME,
    CONF_PHONEBOOK_ID,
    CONF_PREFIXES,
    CONF_TR064_PORT,
    DEFAULT_NAME,
    DOMAIN,
    FRITZ_CALL,
    FRITZ_CONNECT,
    FRITZ_DISCONNECT,
    FRITZ_RING,
)
from .tr064 import FritzTr064Phonebook

_LOGGER = logging.getLogger(__name__)


def _ts_to_iso(ts: str) -> str:
    # Fritz: '28.01.26 09:47:17'
    try:
        dt = datetime.strptime(ts, "%d.%m.%y %H:%M:%S")
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return ts


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


class CallState(StrEnum):
    IDLE = "idle"
    RINGING = "ringing"
    DIALING = "dialing"
    TALKING = "talking"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    host: str = entry.data[CONF_HOST]
    port: int = entry.data["callmonitor_port"]
    name: str = entry.data.get(CONF_NAME, DEFAULT_NAME)

    entity = FritzRawCallSensor(hass, entry, host, port, name)
    async_add_entities([entity])


class FritzRawCallSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(CallState)
    _attr_translation_key = "call_state"

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, host: str, port: int, name: str
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._host = host
        self._port = port
        self._name = name

        self._attr_unique_id = f"{host}:{port}:call_state"
        # self._attr_name = name
        self._attr_native_value = CallState.IDLE

        self._attrs: dict[str, Any] = {}

        self._prefixes: list[str] = entry.options.get(
            CONF_PREFIXES, entry.data.get(CONF_PREFIXES, [])
        )

        self._client = FritzRawCallMonitorClient(host, port, self._handle_line)
        self._phonebook: FritzTr064Phonebook | None = None

        # Persistent diagnostics (NOT stored in _attrs because _attrs is overwritten per event)
        self._phonebook_status: str = "not_loaded"
        self._phonebook_entries: int = 0
        self._phonebook_last_refresh: str | None = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host}:{port}")},
            manufacturer="AVM",
            name="FRITZ!Box",
            configuration_url=f"http://{host}",
        )

    async def async_added_to_hass(self) -> None:
        import aiohttp  # local import to keep requirements empty

        session = aiohttp.ClientSession()
        self.async_on_remove(session.close)

        tr064_port = self._entry.options.get(
            CONF_TR064_PORT, self._entry.data[CONF_TR064_PORT]
        )
        username = self._entry.options.get(CONF_USERNAME, self._entry.data[CONF_USERNAME])
        password = self._entry.options.get(CONF_PASSWORD, self._entry.data[CONF_PASSWORD])
        phonebook_id = self._entry.options.get(
            CONF_PHONEBOOK_ID, self._entry.data[CONF_PHONEBOOK_ID]
        )
        prefixes = self._entry.options.get(CONF_PREFIXES, self._prefixes)
        self._prefixes = prefixes

        self._phonebook = FritzTr064Phonebook(
            host=self._host,
            port=tr064_port,
            username=username,
            password=password,
            phonebook_id=phonebook_id,
            prefixes=prefixes,
            session=session,
        )

        # Initial phonebook load (best-effort)
        try:
            await self._phonebook.refresh()
            self._phonebook_status = "ok"
            self._phonebook_last_refresh = _now_iso()
            self._phonebook_entries = self._phonebook.entries
        except Exception as err:  # noqa: BLE001
            # Mark phonebook as failing (auth/network/etc.)
            self._phonebook_status = f"error:{type(err).__name__}"
            self._phonebook_last_refresh = _now_iso()
            self._phonebook_entries = 0
            self.async_write_ha_state()
            _LOGGER.warning("Name resolution failed: %s", err)

        self.async_write_ha_state()

        await self._client.start()

        self.async_on_remove(
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._ha_stop)
        )

    async def async_will_remove_from_hass(self) -> None:
        await self._client.stop()

    async def _ha_stop(self, _event) -> None:
        await self._client.stop()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # Start from current event attrs
        attrs = dict(self._attrs)

        # Always include prefixes if configured
        if self._prefixes:
            attrs[ATTR_PREFIXES] = self._prefixes

        # Always include phonebook diagnostics
        attrs[ATTR_PHONEBOOK_STATUS] = self._phonebook_status
        attrs[ATTR_PHONEBOOK_ENTRIES] = self._phonebook_entries
        if self._phonebook_last_refresh is not None:
            attrs[ATTR_PHONEBOOK_LAST_REFRESH] = self._phonebook_last_refresh

        return attrs

    @callback
    def _handle_line(self, line: str) -> None:
        parts = line.split(";")
        if len(parts) < 2:
            return

        ts = parts[0]
        kind = parts[1]
        isotime = _ts_to_iso(ts)

        if kind == FRITZ_RING and len(parts) >= 6:
            self._attr_native_value = CallState.RINGING
            self._attrs = {
                ATTR_RAW: line,
                ATTR_TYPE: "incoming",
                ATTR_FROM: parts[3],
                ATTR_TO: parts[4],
                ATTR_DEVICE: parts[5],
                ATTR_INITIATED: isotime,
            }
            self._resolve_names_async(from_number=parts[3], to_number=None, with_number=None)

        elif kind == FRITZ_CALL and len(parts) >= 7:
            self._attr_native_value = CallState.DIALING
            self._attrs = {
                ATTR_RAW: line,
                ATTR_TYPE: "outgoing",
                ATTR_FROM: parts[4],
                ATTR_TO: parts[5],
                ATTR_DEVICE: parts[6],
                ATTR_INITIATED: isotime,
            }
            self._resolve_names_async(from_number=None, to_number=parts[5], with_number=None)

        elif kind == FRITZ_CONNECT and len(parts) >= 5:
            self._attr_native_value = CallState.TALKING
            self._attrs = {
                ATTR_RAW: line,
                ATTR_DEVICE: parts[3],
                ATTR_WITH: parts[4],
                ATTR_ACCEPTED: isotime,
            }
            self._resolve_names_async(from_number=None, to_number=None, with_number=parts[4])

        elif kind == FRITZ_DISCONNECT and len(parts) >= 4:
            self._attr_native_value = CallState.IDLE
            self._attrs = {
                ATTR_RAW: line,
                ATTR_DURATION: parts[3],
                ATTR_CLOSED: isotime,
            }

        self.async_write_ha_state()

    def _resolve_names_async(
        self,
        from_number: str | None,
        to_number: str | None,
        with_number: str | None,
    ) -> None:
        if self._phonebook is None:
            return

        async def _do() -> None:
            try:
                if from_number:
                    c = await self._phonebook.lookup(from_number)
                    if c:
                        self._attrs[ATTR_FROM_NAME] = c.name
                if to_number:
                    c = await self._phonebook.lookup(to_number)
                    if c:
                        self._attrs[ATTR_TO_NAME] = c.name
                if with_number:
                    c = await self._phonebook.lookup(with_number)
                    if c:
                        self._attrs[ATTR_WITH_NAME] = c.name

                self.async_write_ha_state()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Name resolution failed: %s", err)

        asyncio.create_task(_do())