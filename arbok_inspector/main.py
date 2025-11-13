from nicegui import ui

def run():
    ui.run(
        title='Arbok Inspector',
        favicon='🐍',
        dark=True,
        show=True,
        port=8090
    )

if __name__ in {"__main__", "__mp_main__", "arbok_inspector.main"}:
    run()
