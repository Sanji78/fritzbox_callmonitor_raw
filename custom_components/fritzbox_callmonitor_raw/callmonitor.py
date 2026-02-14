from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

_LOGGER = logging.getLogger(__name__)


class FritzRawCallMonitorClient:
    """Raw TCP CallMonitor client (fully async, NO THREADS)."""

    def __init__(self, host: str, port: int, on_line: Callable[[str], None]) -> None:
        self._host = host
        self._port = port
        self._on_line = on_line
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    async def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(
            self._run(), 
            name=f"fritz_callmonitor_{self._host}"
        )

    async def stop(self) -> None:
        self._stop.set()
        
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        """Main connection loop - PURE ASYNC, ZERO THREADS."""
        backoff = 5
        
        while not self._stop.is_set():
            self._reader = None
            self._writer = None
            
            try:
                _LOGGER.debug("Connecting to %s:%s", self._host, self._port)
                
                # ✅ CRITICAL FIX: asyncio.open_connection = NO THREADS!
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self._host, self._port),
                    timeout=15.0
                )
                
                _LOGGER.info("Connected to CallMonitor at %s:%s", self._host, self._port)
                backoff = 5

                # ✅ CRITICAL FIX: Async line reading = NO THREADS!
                while not self._stop.is_set():
                    try:
                        line_bytes = await asyncio.wait_for(
                            self._reader.readuntil(b'\n'),
                            timeout=60.0
                        )
                        
                        line = line_bytes.strip().decode("utf-8", errors="replace")
                        if line:
                            self._on_line(line)
                            
                    except asyncio.TimeoutError:
                        # No data for 60s - check if connection is alive
                        if self._reader.at_eof():
                            raise ConnectionResetError("Connection closed")
                        continue
                    
                    except asyncio.IncompleteReadError:
                        raise ConnectionResetError("Connection closed by peer")

            except asyncio.CancelledError:
                raise
            
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("CallMonitor connection lost: %s", err)
            
            finally:
                if self._writer:
                    try:
                        self._writer.close()
                        await self._writer.wait_closed()
                    except Exception:  # noqa: BLE001
                        pass
                self._reader = None
                self._writer = None

            if self._stop.is_set():
                return

            _LOGGER.debug("Reconnecting in %ss", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 120)