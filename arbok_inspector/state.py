from nicegui import ui
from pathlib import Path
import asyncio
from typing import Optional
import sqlite3
from qcodes.dataset import initialise_or_create_database_at

class ArbokInspector:
    def __init__(self):
        self.database_path: Optional[Path] = None
        self.initial_dialog = None
        self.csonn = None
        self.cursor = None
        
    def connect_database(self):
        self.conn = sqlite3.connect(self.database_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        initialise_or_create_database_at(self.database_path)

    def handle_path_input(self, path_input):
        """Handle manual path input"""
        if path_input.value:
            try:
                file_path = Path(path_input.value)
                if file_path.exists():
                    self.database_path = file_path
                    ui.notify(f'Database path set: {file_path.name}', type='positive')
                    # Only close dialog if path is valid and exists
                    try:
                        self.connect_database()
                        if self.initial_dialog:
                            self.initial_dialog.close()
                        self.show_database_path()
                    except sqlite3.Error as e:
                        ui.notify(f'Error connecting to database: {str(e)}', type='negative')
                        # Don't close dialog - let user try again
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
        # Navigate to a database browser page instead of clearing
        ui.navigate.to('/browser')

# Initialize the application
inspector = ArbokInspector()
inspector.database_path = 'test.db'  # For development purposes only
inspector.connect_database()