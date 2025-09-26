from nicegui import ui
from pathlib import Path
import asyncio
from typing import Optional

from arbok_inspector.state import inspector

from arbok_inspector.pages import greeter, database_browser

if __name__ in {'__main__', '__mp_main__'}:
    ui.run(
        title='Arbok Inspector',
        favicon='🐍',
        dark=None,
        show=True,
        port=8080
    )

