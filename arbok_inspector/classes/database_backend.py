"""Database backend abstraction — eliminates if/else branching on database_type."""
from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine


class DatabaseBackend(ABC):
    """Protocol for database query operations used by the UI layer."""

    @abstractmethod
    def get_days(self, offset_hours: float) -> list[tuple[str, datetime]]:
        """Return (day_string, earliest_timestamp) pairs sorted by day."""

    @abstractmethod
    def get_runs_for_day(
        self, target_day: str, offset_hours: float
    ) -> tuple[list[dict], list[dict]]:
        """Return (row_dicts, column_defs) for runs on the given day."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name for the info panel."""


QCODES_RUN_GRID_COLUMN_DEFS = [
    {'headerName': 'Run ID', 'field': 'run_id', "width": 50},
    {'headerName': 'Name', 'field': 'name'},
    {'headerName': 'Experiment', 'field': 'experiment_name'},
    {'headerName': '# Results', 'field': 'result_counter', "width": 50},
    {'headerName': 'Started', 'field': 'run_timestamp', "width": 50},
    {'headerName': 'Finish', 'field': 'completed_timestamp', "width": 50},
]

NATIVE_RUN_GRID_COLUMN_DEFS = [
    {'headerName': 'Run ID', 'field': 'run_id', "width": 50},
    {'headerName': 'Name', 'field': 'name'},
    {'headerName': 'Experiment', 'field': 'experiment'},
    {'headerName': '# results', 'field': 'result_count', "width": 60},
    {'headerName': '# batches', 'field': 'batch_count', "width": 60},
    {'headerName': 'started', 'field': 'start_time', "width": 60},
    {'headerName': 'last result', 'field': 'completed_time', "width": 60},
]

NATIVE_COLUMNS = {
    'run_id': 'run ID',
    'name': 'name',
    'result_count': '# results',
    'batch_count': '# batches',
    'start_time': 'started',
    'completed_time': 'last result',
    'is_completed': 'completed'
}


class QcodesBackend(DatabaseBackend):
    """QCoDeS SQLite database backend."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    @property
    def display_name(self) -> str:
        return str(self.db_path)

    def get_days(self, offset_hours: float) -> list[tuple[str, datetime]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    day,
                    MIN(run_timestamp) AS earliest_ts
                FROM (
                    SELECT
                        run_timestamp,
                        DATE(datetime(run_timestamp, 'unixepoch', ? || ' hours')) AS day
                    FROM runs
                )
                GROUP BY day
                ORDER BY day;
            """, (offset_hours,))
            return cursor.fetchall()
        finally:
            conn.close()

    def get_runs_for_day(
        self, target_day: str, offset_hours: float
    ) -> tuple[list[dict], list[dict]]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        hours = int(offset_hours)
        minutes = int((offset_hours - hours) * 60)
        offset_str = f"{'+' if offset_hours >= 0 else '-'}{abs(hours):02d}:{abs(minutes):02d}"

        exclude_columns = {
            'qua_program', 'snapshot', 'run_description',
            'measurement_exception', 'parameters'
        }
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(runs)")
            columns = cursor.fetchall()
            all_columns = [
                col['name'] for col in columns
                if col['name'] not in exclude_columns
            ]
            columns_str = ", ".join(f"r.{col}" for col in all_columns)
            query = f"""
                SELECT {columns_str}, e.name AS experiment_name
                FROM runs r
                JOIN experiments e ON r.exp_id = e.exp_id
                WHERE DATE(datetime(r.run_timestamp, 'unixepoch', '{offset_str}')) = ?
                ORDER BY r.run_timestamp;
            """
            cursor.execute(query, (target_day,))
            rows = [dict(row) for row in cursor.fetchall()]
            return rows, QCODES_RUN_GRID_COLUMN_DEFS
        finally:
            conn.close()


class NativeArbokBackend(DatabaseBackend):
    """Native Arbok PostgreSQL + MinIO backend."""

    def __init__(self, engine: Engine):
        self.engine = engine

    @property
    def display_name(self) -> str:
        return str(self.engine.url)

    def get_days(self, offset_hours: float) -> list[tuple[str, datetime]]:
        query = text("""
            SELECT
                day,
                MIN(start_time) AS earliest_ts
            FROM (
                SELECT
                    start_time,
                    (to_timestamp(start_time) + (:offset_hours || ' hours')::interval)::date AS day
                FROM runs
            ) AS sub
            GROUP BY day
            ORDER BY day;
        """)
        with self.engine.connect() as conn:
            result = conn.execute(query, {"offset_hours": offset_hours})
            return result.fetchall()

    def get_runs_for_day(
        self, target_day: str, offset_hours: float
    ) -> tuple[list[dict], list[dict]]:
        query = text("""
            SELECT r.*, e.name AS experiment_name
            FROM runs r
            JOIN experiments e ON r.exp_id = e.exp_id
            WHERE (to_timestamp(r.start_time) + (:offset_hours || ' hours')::interval)::date = :target_day
            ORDER BY r.start_time;
        """)
        with self.engine.connect() as conn:
            result = conn.execute(
                query, {"offset_hours": offset_hours, "target_day": target_day}
            )
            runs_filtered = [
                {**{col: row[col] for col in NATIVE_COLUMNS.keys()},
                 "experiment": row["experiment_name"]}
                for row in result.mappings()
            ]
        return runs_filtered, NATIVE_RUN_GRID_COLUMN_DEFS
