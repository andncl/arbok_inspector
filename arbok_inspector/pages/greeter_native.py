"""Greeter page for native Arbok (PostgreSQL + MinIO) connection."""
from nicegui import ui
from arbok_inspector.state import inspector

ARBOK_GREEN = '#4BA701'


@ui.page('/')
async def greeter_page() -> None:
    """Native Arbok credentials dialog."""
    with ui.dialog().classes('width=800px') as dialog:
        dialog.props('persistent')
        with ui.card().style('min-width: 300px; max-width: 600px'):
            inspector.initial_dialog = dialog
            with ui.column().classes('items-center w-full'):
                ui.label('Arbok Inspector 🐍🔎').classes(
                    'text-4xl text-center mb-6')
            ui.markdown(
                'Enter credentials to your native PostgreSQL database '
                'and MinIO server. Visit '
                '[arbok-database](https://github.com/andncl/arbok_database) '
                'for more info.'
            ).classes('text-body1 mb-4')

            database_url = ui.input(
                label='Database address',
                placeholder=(
                    'postgresql+psycopg2://<user>:<pass>@<host>:<port>/<db>')
            ).classes('w-full mb-2')

            minio_url = ui.input(
                label='MinIO address',
                value='http://localhost:9000',
            ).classes('w-full mb-2')

            minio_user = ui.input(
                label='MinIO username',
                value='minioadmin'
            ).classes('w-full mb-2')

            minio_password = ui.input(
                label='MinIO password',
                value='minioadmin',
                password=True
            ).classes('w-full mb-2')

            minio_bucket = ui.input(
                label='MinIO bucket',
                placeholder='dev',
            ).classes('w-full')

            ui.button(
                text='Connect',
                on_click=lambda: inspector.connect_to_arbok_database(
                    database_url.value,
                    minio_url.value,
                    minio_user.value,
                    minio_password.value,
                    minio_bucket.value),
                icon='folder_open',
                color=ARBOK_GREEN).classes('mb-4 w-full')
    dialog.open()
