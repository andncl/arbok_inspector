
from nicegui import ui
from arbok_inspector.state import inspector

@ui.page('/')
async def greeter_page() -> None:
    """Main page that starts with database selection"""
    with ui.dialog().classes('width=800px') as dialog:
        dialog.props('persistent ') # width=800px max-width=90vw overflow-y-auto max-h-[90vh]

        with ui.card().style('min-width: 300px; max-width: 1000px'):
            inspector.initial_dialog = dialog
            with ui.column().classes('items-center w-full justify-between max-w-5xl'):
                ui.label('Welcome to Arbok Inspector 🐍🔎').classes(
                    'text-4xl  text-center mb-6'
                )
                ui.label('Pick your database type:').classes(
                    'text-2xl font-bold text-center mb-6'
                )
            with ui.row().classes('w-full gap-4 items-stretch'):
                with ui.card().classes('flex-1'):
                    build_qcodes_connection_section()

                with ui.card().classes('flex-1 gap-4'):
                    build_native_arbok_connection_section()
    dialog.open()

def build_qcodes_connection_section() -> None:
    """Build the QCoDeS database connection section."""
    ui.label('Please enter the path to your QCoDeS database file'
            ).classes('text-body1 mb-4')
    ui.image('https://microsoft.github.io/Qcodes/_images/qcodes_logo.png')
    #ui.label('Database File Path').classes('text-subtitle2 mb-2')
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
    # ui.label('Enter credentials to your native postgresql database and minio server'
    #         ).classes('text-body1 mb-4')
    # ui.markdown('Visit [arbok-database](https://github.com/andncl/arbok_database) for more info.')
    ui.markdown(
        'Enter credentials to your native PostgreSQL database and MinIO server. '
        'Visit [arbok-database](https://github.com/andncl/arbok_database) for more info.' 
    ).classes('text-body1 mb-4')
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