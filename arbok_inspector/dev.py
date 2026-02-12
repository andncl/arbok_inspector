"""
Module containing launching script for the arbok-inspector in editable mode

This needs to be separate from the 'main' script since nicegui doesnt allow
indirect entry points when launching in editable mode (reload).

Hence we are using dev:run and not main:main
"""
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

def main() -> None:
    run()

if __name__ in {"__main__", "__mp_main__"}:
    main()
