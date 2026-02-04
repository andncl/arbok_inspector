"""Module containing launching script for main application"""

import argparse
from nicegui import ui

from arbok_inspector.state import inspector
from arbok_inspector.pages import greeter, database_browser, run_view

def run(port: int = 8090) -> None:
    ui.run(
        title='Arbok Inspector',
        favicon='🐍',
        dark=True,
        show=True,
        port=port,
        reload=False,
    )

def main() -> None:
    parser = argparse.ArgumentParser(description='Run Arbok Inspector')
    parser.add_argument(
        '--port',
        type=int,
        default=8090,
        help='Port to run the server on (default: 8090)',
    )
    args = parser.parse_args()
    run(port=args.port)

if __name__ in {"__main__", "__mp_main__"}:
    main()
