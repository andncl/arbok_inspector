from nicegui import ui

from arbok_inspector.state import inspector
from arbok_inspector.pages import database_browser, greeter, run_view

def run():
    ui.run(
        title='Arbok Inspector',
        favicon='🐍',
        dark=True,
        show=True,
        port=8090,
        reload = True
    )

if __name__ in {"__main__", "__mp_main__"}:
    run()
