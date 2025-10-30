from nicegui import ui
from pathlib import Path
import asyncio
from typing import Optional

from arbok_inspector.state import inspector

from arbok_inspector.pages import greeter, database_browser

def main():
    ui.run(
        title='Arbok Inspector',
        favicon='🐍',
        dark=True,
        show=True,
        port=8090
    )

# # Optional: keep this so you can run directly during development
if __name__ in {"__main__", "__mp_main__"}:
    main()