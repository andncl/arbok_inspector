from nicegui import ui

from arbok_inspector.state import inspector
from arbok_inspector.pages import greeter, database_browser

def run():
    ui.run(
        title='Arbok Inspector',
        favicon='🐍',
        dark=True,
        show=True,
        port=8090
    )

run()
