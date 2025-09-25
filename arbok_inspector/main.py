from nicegui import ui
from pathlib import Path
import asyncio
from typing import Optional

class ArbokInspector:
    def __init__(self):
        self.database_path: Optional[Path] = None
        self.initial_dialog = None
        
    def handle_path_input(self, path_input):
        """Handle manual path input"""
        if path_input.value:
            try:
                file_path = Path(path_input.value)
                if file_path.exists():
                    self.database_path = file_path
                    ui.notify(f'Database path set: {file_path.name}', type='positive')
                    # Only close dialog if path is valid and exists
                    if self.initial_dialog:
                        self.initial_dialog.close()
                    self.show_database_path()
                else:
                    ui.notify('File does not exist', type='negative')
                    # Don't close dialog - let user try again
            except Exception as ex:
                ui.notify(f'Error: {str(ex)}', type='negative')
                # Don't close dialog on error
        else:
            ui.notify('Please enter a file path', type='warning')
            # Don't close dialog if no path entered
    
    def show_database_path(self):
        """Display the database path on the main page"""
        # Navigate to a results page instead of clearing
        ui.navigate.to('/results')

# Initialize the application
inspector = ArbokInspector()

@ui.page('/')
async def main_page():
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

@ui.page('/results')
def results_page():
    """Results page showing the selected database"""
    ui.add_head_html('<title>Arbok Inspector - Results</title>')
    
    with ui.column().classes('w-full max-w-2xl mx-auto mt-8 p-4'):
        ui.label('Arbok Inspector').classes('text-3xl font-bold mb-6')
        
        with ui.card().classes('w-full p-6'):
            ui.label('Database Information').classes('text-xl font-semibold mb-4')
            if inspector.database_path:
                ui.label(f'Database Path: {str(inspector.database_path)}').classes('text-lg')
            else:
                ui.label('No database selected').classes('text-lg text-red-500')
            
            # Button to select a new database
            ui.button('Select New Database', 
                     on_click=lambda: ui.navigate.to('/'),
                     color='purple').classes('mt-4')

if __name__ in {'__main__', '__mp_main__'}:
    ui.run(
        title='Arbok Inspector',
        favicon='🐍',
        dark=None,
        show=True,
        port=8080
    )

# conn = sqlite3.connect(r"G:\rf2v_data\tls\tls_september.db")
# cursor = conn.cursor()
# cursor.execute("""
#     SELECT 
#         day,
#         MIN(run_timestamp) AS earliest_ts
#     FROM (
#         SELECT 
#             run_timestamp,
#             DATE(datetime(run_timestamp, 'unixepoch')) AS day
#         FROM runs
#     )
#     GROUP BY day
#     ORDER BY day;
# """)

# rows = cursor.fetchall()

# for day, ts in rows:
#     print(day, datetime.fromtimestamp(ts))