
from nicegui import ui
from arbok_inspector.state import inspector

@ui.page('/')
async def greeter_page() -> None:
    """Main page that starts with file selection"""
    ui.add_head_html('<title>Arbok Inspector 🐍</title>')

    # Show initial file selection dialog
    with ui.dialog() as dialog:
        dialog.props('persistent')
        with ui.card().classes('p-6 max-w-5xl w-auto'):
            inspector.initial_dialog = dialog
            dialog.props('persistent width=800px max-width=90vw')
            with ui.row().classes('items-start w-full justify-between max-w-5xl'):
                ui.label('Welcome to Arbok Inspector').classes('text-h6 mb-4')
                ui.image('https://microsoft.github.io/Qcodes/_images/qcodes_logo.png')
                with ui.card().classes('w-[30%]'):
                    build_qcodes_connection_section()

                with ui.card().classes('w-[65%] gap-1'):
                    build_native_arbok_connection_section()
    dialog.open()

def build_qcodes_connection_section() -> None:
    """Build the QCoDeS database connection section."""
    ui.label('Please enter the path to your QCoDeS database file'
            ).classes('text-body1 mb-4')
    ui.label('Database File Path').classes('text-subtitle2 mb-2')
    path_input = ui.input(
        label='Database file path',
        placeholder='C:/path/to/your/database.db'
    ).classes('w-full mb-2')
    ui.button(
        text = 'Load Database',
        on_click=lambda: inspector.connect_to_qcodes_database(path_input),
        icon='folder_open',
        color='purple').classes('mb-4 w-full')
    ui.separator()
    ui.label('Supported formats: .db, .sqlite, .sqlite3'
            ).classes('text-caption text-grey')

def build_native_arbok_connection_section() -> None:
    ui.label('Enter credentials to your native postgresql database and minio server'
            ).classes('text-body1 mb-4')
    ui.markdown('Visit [arbok-database](https://github.com/andncl/arbok_database) for more info.')

    database_url = ui.input(
        label='Database address',
        placeholder='"postgresql+psycopg2://<username>:<password>@<host>:<port>/<database>"'
    ).classes('w-full mb-2')

    minio_url = ui.input(
        label='MiniO address',
        value='http://localhost:9000',
    ).classes('w-full mb-2')

    minio_user = ui.input(
        label='MiniO username',
        value='minioadmin'
    ).classes('w-full mb-2')

    minio_password = ui.input(
        label='MiniO password',
        value='minioadmin',
        password=True
    ).classes('w-full')

    minio_bucket = ui.input(
        label='MiniO bucket',
        placeholder='dev',
    ).classes('w-full')

    ui.button(
        text = 'Connect Database and bucket',
        on_click=lambda: inspector.connect_to_arbok_database(
            database_url.value,
            minio_url.value,
            minio_user.value,
            minio_password.value,
            minio_bucket.value
            ),
        icon='folder_open',
        color='#4BA701').classes('mb-4 w-full')