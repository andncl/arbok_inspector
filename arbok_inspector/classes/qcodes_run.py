"""Module containing QcodesRun class"""
from __future__ import annotations
from typing import TYPE_CHECKING

import os
from pathlib import Path

from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import get_DB_location
from arbok_inspector.classes.base_run import BaseRun

if TYPE_CHECKING:
    from xarray import Dataset

COLUMN_LABELS = {}

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
        
    def _load_dataset(self) -> Dataset:
        dataset = load_by_id(self.run_id)
        dataset = dataset.to_xarray_dataset()
        return dataset

    def _get_database_columns(self) -> dict[str, dict[str, str]]:
        self.inspector.cursor.execute(
            "SELECT * FROM runs WHERE run_id = ?", (self.run_id,))
        row = self.inspector.cursor.fetchone()
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
        db_dir = os.path.dirname(db_path)
        programs_dir = Path(db_dir) / "qua_programs/"
        raise NotImplementedError
        ### TODO: IMPLEMENT MORE EASILY IN ARBOK THOUGH!
        # if not os.path.isdir(programs_dir):
        #     os.makedirs(programs_dir)
        # try:
        #     with open(save_path, 'r', encoding="utf-8") as file:
        #         file.write(
        #             generate_qua_script(qua_program, opx_config))
        # except FileNotFoundError as e:
        #     ui.notify(f"Qua program couldnt be found next to database: {e}")