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
        
    def load_dataset(self) -> Dataset:
        dataset = load_by_id(self.run_id)
        dataset = dataset.to_xarray_dataset()

    def get_qua_code(self, as_string: bool = False) -> str | bytes:
        db_path = os.path.abspath(get_DB_location())
        db_dir = os.path.dirname(db_path)
        programs_dir = Path(db_dir) / "qua_programs/"
        raise NotImplementedError
        # if not os.path.isdir(programs_dir):
        #     os.makedirs(programs_dir)
        # try:
        #     with open(save_path, 'r', encoding="utf-8") as file:
        #         file.write(
        #             generate_qua_script(qua_program, opx_config))
        # except FileNotFoundError as e:
        #     ui.notify(f"Qua program couldnt be found next to database: {e}")