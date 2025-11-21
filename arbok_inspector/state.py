from nicegui import ui
from pathlib import Path
import asyncio
from typing import Optional

from qcodes.dataset import initialise_or_create_database_at

import fsspec
import sqlite3
from sqlalchemy import create_engine, select, func

class ArbokInspector:
    def __init__(self):
        self.qcodes_database_path: Optional[Path] = None
        self.initial_dialog = None
        self.database_type = None  # 'qcodes' or 'arbok'

        self.qcodes_database_path = None
        self.conn = None
        self.cursor = None
        self.database_engine = None
        self.minio_filesystem = None
        self.minio_bucket = None
        
    def connect_qcodes_database(self):
        self.conn = sqlite3.connect(self.qcodes_database_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        initialise_or_create_database_at(self.qcodes_database_path)

    def connect_to_qcodes_database(self, path_input) -> None:
        """Connect to a QCoDeS database given a file path input widget."""
        self.database_engine = None
        self.minio_filesystem = None
        self.minio_bucket = None
        if path_input.value is None:
            ui.notify('Please enter a file path', type='warning')
            return
        try:
            file_path = Path(path_input.value)
            if file_path.exists():
                self.qcodes_database_path = file_path
                ui.notify(f'Database path set: {file_path.name}', type='positive')
                try:
                    self.connect_qcodes_database()
                    if self.initial_dialog:
                        self.initial_dialog.close()
                    self.database_type = 'qcodes'
                    ui.navigate.to('/browser')
                except sqlite3.Error as e:
                    ui.notify(f'Error connecting to database: {str(e)}', type='negative')
            else:
                ui.notify('File does not exist', type='negative')
        except Exception as ex:
            ui.notify(f'Error: {str(ex)}', type='negative')
        self.database_type = 'qcodes'
    
    def connect_to_arbok_database(
        self,
        database_url: str,
        minio_url: str,
        minio_user: str,
        minio_password: str,
        minio_bucket: str) -> None:
        """
        Connect to a native Arbok database given connection parameters.
        
        Args:
            database_url (str): The database connection URL.
            minio_url (str): The MinIO server URL.
            minio_user (str): The MinIO username.
            minio_password (str): The MinIO password.
            minio_bucket (str): The MinIO bucket name.
        """
        self.qcodes_database_path = None
        self.conn = None
        self.cursor = None
        try:
            self.database_engine = create_engine(database_url)
        except Exception as ex:
            ui.notify(f'Error creating database engine: {str(ex)}', type='negative')
            return

        try:
            self.minio_filesystem = fsspec.filesystem(
                protocol = "s3",
                client_kwargs={"endpoint_url": minio_url},
                key=minio_user,
                secret=minio_password
                )
        except Exception as ex:
            ui.notify(f'Error connecting to MinIO: {str(ex)}', type='negative')
            return
        if self.initial_dialog:
            self.initial_dialog.close()
        self.database_type = 'native_arbok'
        self.minio_bucket = minio_bucket
        ui.navigate.to('/browser')
    
inspector = ArbokInspector()
