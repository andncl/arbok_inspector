from nicegui import ui
from pathlib import Path
import asyncio
from typing import Optional

from arbok_inspector.state import inspector
from arbok_inspector.pages import greeter, database_browser

ui.run(
    title='Arbok Inspector',
    favicon='🐍',
    dark=True,
    show=True,
    port=8090
)
