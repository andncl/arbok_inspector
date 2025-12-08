"""Module containing QcodesRun class"""
from __future__ import annotations
from typing import TYPE_CHECKING

import os
from functools import wraps
from pathlib import Path
import sqlite3

from nicegui import app, ui
from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import get_DB_location
from qcodes import config as qc_config
from qcodes.dataset.sqlite.database import initialise_or_create_database_at, connect

from arbok_inspector.classes.base_run import BaseRun

if TYPE_CHECKING:
    from xarray import Dataset

COLUMN_LABELS = {}

def with_sqlite_connection(func):
    """
    Decorator that creates a SQLite connection, passes it to the function,
    and closes it automatically.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        db_path = self.db_path
        qc_config["core"]["db_location"] = db_path
        initialise_or_create_database_at(db_path)
        with connect(db_path, debug=False) as conn:
            # Pass the connection to the decorated function
            return func(self, conn, *args, **kwargs)
    return wrapper

class QcodesRun(BaseRun):
    """"""
    def __init__(
        self,
        run_id: int
    ):
        """
        Constructor for QcodesRun class
        
        Args:
            run_id (int): Run ID of the measurement run
        """
        super().__init__(run_id)
        self.db_path = app.storage.tab["qcodes_db_path"]

    @with_sqlite_connection
    def _load_dataset(self, conn) -> Dataset:
        """Load the xarray Dataset for the run from the QCoDeS database."""
        dataset = load_by_id(self.run_id, conn=conn)
        dataset = dataset.to_xarray_dataset(use_multi_index = 'never')
        return dataset

    @with_sqlite_connection
    def _get_database_columns(self, conn) -> dict[str, dict[str, str]]:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM runs WHERE run_id = ?", (self.run_id,))
        row = cursor.fetchone()
        if row is not None:
            row_dict = dict(row)
        else:
            raise ValueError(f'database entry not found for run-ID: {self.run_id}')
        columns_and_values = {}
        for key, value in row_dict.items():
            columns_and_values[key] = {'value': value}
            if key in COLUMN_LABELS:
                label = COLUMN_LABELS[key]
                columns_and_values[key]['label'] = label
        return columns_and_values

    def get_qua_code(self, as_string: bool = False) -> str | bytes:
        db_path = os.path.abspath(get_DB_location())
        db_name = db_path.split('/')[-1].split('.db')[0]
        db_dir = os.path.dirname(db_path)
        programs_dir = Path(db_dir) / f"qua_programs__{db_name}/"
        program_dir = programs_dir / f"{self.run_id}.py"
        #raise NotImplementedError
        ### TODO: IMPLEMENT MORE EASILY IN ARBOK THOUGH!
        try:
            if not os.path.isdir(programs_dir):
                os.makedirs(programs_dir)
            with open(program_dir, 'r', encoding="utf-8") as file:
                file_contents = file.read()
        except FileNotFoundError as e:
            ui.notify(f"Qua program couldnt be found next to database: {e}")
            file_contents = ""
        return file_contents
