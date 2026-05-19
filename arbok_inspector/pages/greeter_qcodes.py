"""Greeter page for QCoDeS database connection."""
from tkinter import Tk, filedialog

from nicegui import ui, run
from arbok_inspector.state import inspector

ARBOK_GREEN = '#4BA701'
ARBOK_PURPLE = 'purple'


@ui.page('/')
async def greeter_page() -> None:
    """QCoDeS database file picker dialog."""
    with ui.dialog().classes('width=800px') as dialog:
        dialog.props('persistent')
        with ui.card().style('min-width: 300px; max-width: 600px'):
            inspector.initial_dialog = dialog
            with ui.column().classes('items-center w-full'):
                ui.label('Arbok Inspector 🐍🔎').classes(
                    'text-4xl text-center mb-6')
                ui.separator()
                ui.image(
                    'https://microsoft.github.io/Qcodes/_images/qcodes_logo.png'
                ).classes('w-64')
                ui.separator()
            ui.label('Select your QCoDeS database file:').classes(
                'mt-6')
            with ui.row().classes('w-full items-center gap-2'):
                path_input = ui.input(
                    label='Database file path',
                    placeholder='C:/path/to/your/database.db'
                ).classes('flex-grow').props('dense')
                ui.button(
                    text='',
                    icon='folder',
                    color=ARBOK_PURPLE,
                    on_click=lambda _: choose_file(path_input))
            ui.button(
                text='Load Database',
                on_click=lambda: inspector.connect_to_qcodes_database(
                    path_input.value),
                icon='folder_open',
                color=ARBOK_GREEN).classes('mb-4 w-full')
            ui.separator()
            ui.label('Supported formats: .db, .sqlite, .sqlite3'
                     ).classes('text-caption text-grey')
    dialog.open()


def open_file_dialog():
    root = Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    path = filedialog.askopenfilename()
    root.destroy()
    return path


async def choose_file(path_input: ui.input) -> None:
    path = await run.io_bound(open_file_dialog)
    if path:
        path_input.value = path
