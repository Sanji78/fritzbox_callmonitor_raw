from __future__ import annotations

import asyncio
import logging
import socket
from typing import Callable, Optional

_LOGGER = logging.getLogger(__name__)


def _enable_keepalive(sock: socket.socket) -> None:
    """Enable TCP keepalive (best-effort)."""
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    except OSError:
        return

    # Linux-specific tuning (best-effort)
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 15)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 4)
    except OSError:
        pass


class FritzRawCallMonitorClient:
    """Raw TCP CallMonitor client (async)."""

    def __init__(self, host: str, port: int, on_line: Callable[[str], None]) -> None:
        self._host = host
        self._port = port
        self._on_line = on_line
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name=f"fritz_raw_callmonitor_{self._host}")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        backoff = 5
        while not self._stop.is_set():
            sock: socket.socket | None = None
            try:
                _LOGGER.debug("Connecting to %s:%s", self._host, self._port)
                sock = await asyncio.to_thread(socket.create_connection, (self._host, self._port), 15)
                _enable_keepalive(sock)
                sock.settimeout(30)

                _LOGGER.info("Connected to CallMonitor at %s:%s", self._host, self._port)
                backoff = 5
                buf = b""

                while not self._stop.is_set():
                    try:
                        chunk = await asyncio.to_thread(sock.recv, 4096)
                    except socket.timeout:
                        continue

                    if not chunk:
                        raise ConnectionResetError("Socket closed by peer")

                    buf += chunk
                    while b"\n" in buf:
                        line_bytes, buf = buf.split(b"\n", 1)
                        line = line_bytes.strip().decode("utf-8", errors="replace")
                        if line:
                            self._on_line(line)

            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("CallMonitor connection lost: %s", err)
            finally:
                if sock is not None:
                    try:
                        sock.close()
                    except OSError:
                        pass

            if self._stop.is_set():
                return

            _LOGGER.debug("Reconnecting in %ss", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 120)