from nicegui import ui
from pathlib import Path
from typing import Optional

from qcodes.dataset import initialise_or_create_database_at

import fsspec
import sqlite3
from sqlalchemy import create_engine

from arbok_inspector.classes.database_backend import (
    DatabaseBackend, QcodesBackend, NativeArbokBackend
)


class ArbokInspector:
    def __init__(self):
        self.qcodes_database_path: Optional[Path] = None
        self.initial_dialog = None
        self.database_type = None  # 'qcodes' or 'native_arbok'
        self.conn = None
        self.cursor = None
        self.database_engine = None
        self.minio_filesystem = None
        self.minio_bucket = None
        self.backend: Optional[DatabaseBackend] = None

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
        self.backend = None
        if path_input is None:
            ui.notify('Please enter a file path', type='warning')
            return
        try:
            file_path = Path(path_input)
            if file_path.exists():
                self.qcodes_database_path = file_path
                ui.notify(f'Database path set: {file_path.name}', type='positive')
                try:
                    self.connect_qcodes_database()
                    if self.initial_dialog:
                        self.initial_dialog.close()
                    self.database_type = 'qcodes'
                    self.backend = QcodesBackend(file_path)
                    ui.navigate.to('/browser')
                except sqlite3.Error as e:
                    ui.notify(f'Error connecting to database: {str(e)}', type='negative')
            else:
                ui.notify('File does not exist', type='negative')
        except Exception as ex:
            ui.notify(f'Error: {str(ex)}', type='negative')

    def connect_to_arbok_database(
        self,
        database_url: str,
        minio_url: str,
        minio_user: str,
        minio_password: str,
        minio_bucket: str) -> None:
        """Connect to a native Arbok database given connection parameters."""
        self.qcodes_database_path = None
        self.conn = None
        self.cursor = None
        self.backend = None
        try:
            self.database_engine = create_engine(database_url)
        except Exception as ex:
            ui.notify(f'Error creating database engine: {str(ex)}', type='negative')
            return

        try:
            self.minio_filesystem = fsspec.filesystem(
                protocol="s3",
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
        self.backend = NativeArbokBackend(self.database_engine)
        ui.navigate.to('/browser')


inspector = ArbokInspector()
