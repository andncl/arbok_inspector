
from nicegui import ui
from arbok_inspector.state import inspector

@ui.page('/')
async def greeter_page():
    """Main page that starts with file selection"""
    ui.add_head_html('<title>Arbok Inspector 🐍</title>')

    # Show initial file selection dialog
    with ui.dialog() as dialog, ui.card().classes('w-96'):
        # Store dialog reference so we can close it later
        inspector.initial_dialog = dialog
        dialog.props('persistent')

        ui.label('Welcome to Arbok Inspector').classes('text-h6 mb-4')
        ui.image('https://microsoft.github.io/Qcodes/_images/qcodes_logo.png')
        ui.label('Please enter the path to your QCoDeS database file'
                 ).classes('text-body1 mb-4')
        ui.label('Database File Path').classes('text-subtitle2 mb-2')
        path_input = ui.input(
            label='Database file path',
            placeholder='C:/path/to/your/database.db'
        ).classes('w-full mb-2')
        ui.button(
            text = 'Load Database',
            on_click=lambda: inspector.handle_path_input(path_input),
            icon='folder_open',
            color='purple').classes('mb-4 w-full')
        ui.separator()
        ui.label('Supported formats: .db, .sqlite, .sqlite3'
                 ).classes('text-caption text-grey')
    
    # Auto-open the dialog
    dialog.open()