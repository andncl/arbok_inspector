"""Module containing NativeRun class"""
from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session
from sqlalchemy.inspection import inspect
import xarray as xr

from arbok_inspector.state import inspector
from arbok_inspector.classes.base_run import BaseRun
from arbok_inspector.classes.models import SqlRun

if TYPE_CHECKING:
    from xarray import Dataset

COLUMN_LABELS = {}


class NativeRun(BaseRun):
    def __init__(self, run_id: int):
        super().__init__(run_id, inspector)

    def _get_database_columns(self) -> dict[str, dict[str, str]]:
        """Returns column names of database, with this row's values and shown labels."""
        columns_and_values = {}
        with Session(self.inspector.database_engine) as session:
            self.sql_run = session.get(SqlRun, self.run_id)
            columns_and_values['experiment'] = {
                'value': self.sql_run.experiment.name}
            for attr in inspect(self.sql_run).mapper.column_attrs:
                value = getattr(self.sql_run, attr.key)
                columns_and_values[attr.key] = {'value': value}
                if attr.key in COLUMN_LABELS:
                    label = COLUMN_LABELS[attr.key]
                    columns_and_values[attr.key]['label'] = label
            session.expunge(self.sql_run)
        return columns_and_values

    def _load_dataset(self) -> Dataset:
        """Load the dataset from the MinIO bucket."""
        minio_path = self.inspector.minio_bucket + "/"
        minio_path += f"{self.sql_run.run_id}_{self.sql_run.uuid}"
        minio_path += "/data.zarr"
        store = self.inspector.minio_filesystem.get_mapper(minio_path)
        dataset = xr.open_zarr(store, consolidated=True)
        return dataset

    def get_qua_code(self, as_string: bool = False) -> str:
        """Retrieve the QUA code associated with this run."""
        import io
        minio_path = self.inspector.minio_bucket + "/"
        minio_path += f"{self.sql_run.run_id}_{self.sql_run.uuid}"
        minio_path += "/metadata/qua_program.py"
        if as_string:
            with self.inspector.minio_filesystem.open(minio_path, mode="r") as f:
                return f.read()
        else:
            with self.inspector.minio_filesystem.open(minio_path, mode="rb") as f:
                return io.BytesIO(f.read())
