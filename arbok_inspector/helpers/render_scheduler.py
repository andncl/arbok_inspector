"""Coalescing scheduler that serializes plot renders of one run view."""
from __future__ import annotations
from typing import Awaitable, Callable

import asyncio
import logging

logger = logging.getLogger(__name__)


class RenderScheduler:
    """
    Runs an async render callback with "latest request wins" semantics.

    At most one render runs at a time. Requests arriving while a render is in
    progress are merged into a single follow-up render, so a burst of slider
    events results in one extra render with the newest state instead of a
    backlog of stale ones. A pending reload request is never dropped by merging.
    No UI imports — the render callback owns all UI handling.
    """

    def __init__(self, render: Callable[[bool], Awaitable[None]]):
        """
        Args:
            render: Coroutine function called with `reload` (bool) that
                performs one complete render.
        """
        self._render = render
        self._pending: bool = False
        self._pending_reload: bool = False
        self._task: asyncio.Task | None = None
        self._closed: bool = False

    @property
    def busy(self) -> bool:
        """True while a render is running or queued."""
        return self._task is not None and not self._task.done()

    def request(self, reload: bool = False) -> None:
        """
        Request a render. Starts one immediately if idle, otherwise marks a
        follow-up render that runs as soon as the current one finished.

        Args:
            reload: Whether the dataset should be reloaded before rendering.
        """
        if self._closed:
            return
        self._pending = True
        self._pending_reload = self._pending_reload or reload
        if not self.busy:
            self._task = asyncio.get_running_loop().create_task(self._run())

    async def wait_idle(self) -> None:
        """Wait until all requested renders have finished."""
        while self.busy:
            await asyncio.shield(self._task)

    def close(self) -> None:
        """Drop pending requests and cancel the running render."""
        self._closed = True
        self._pending = False
        if self.busy:
            self._task.cancel()

    async def _run(self) -> None:
        while self._pending and not self._closed:
            reload = self._pending_reload
            self._pending = False
            self._pending_reload = False
            try:
                await self._render(reload)
            except Exception:  # pylint: disable=broad-except
                logger.exception("Render failed")
