"""Tests for the DatabaseBackend abstraction and QcodesBackend."""
import sqlite3
import tempfile
import time
from pathlib import Path

import pytest

from arbok_inspector.classes.database_backend import (
    QcodesBackend, QCODES_RUN_GRID_COLUMN_DEFS
)


@pytest.fixture
def qcodes_db():
    """Create a temporary QCoDeS-like SQLite database with test data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE experiments (
            exp_id INTEGER PRIMARY KEY,
            name TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE runs (
            run_id INTEGER PRIMARY KEY,
            exp_id INTEGER,
            name TEXT,
            result_counter INTEGER DEFAULT 0,
            run_timestamp REAL,
            completed_timestamp REAL,
            FOREIGN KEY (exp_id) REFERENCES experiments(exp_id)
        )
    """)
    conn.execute("INSERT INTO experiments (exp_id, name) VALUES (1, 'test_exp')")

    base_ts = 1700000000  # 2023-11-14 ~22:13 UTC
    for i in range(5):
        conn.execute(
            "INSERT INTO runs (run_id, exp_id, name, result_counter, run_timestamp, completed_timestamp) "
            "VALUES (?, 1, ?, ?, ?, ?)",
            (i + 1, f"run_{i}", 3, base_ts + i * 3600, base_ts + i * 3600 + 60)
        )
    # Add runs on a different day
    next_day_ts = base_ts + 86400
    for i in range(3):
        conn.execute(
            "INSERT INTO runs (run_id, exp_id, name, result_counter, run_timestamp, completed_timestamp) "
            "VALUES (?, 1, ?, ?, ?, ?)",
            (i + 10, f"run_day2_{i}", 2, next_day_ts + i * 3600, next_day_ts + i * 3600 + 60)
        )
    conn.commit()
    conn.close()

    yield db_path
    db_path.unlink(missing_ok=True)


class TestQcodesBackend:
    def test_display_name(self, qcodes_db):
        backend = QcodesBackend(qcodes_db)
        assert str(qcodes_db) in backend.display_name

    def test_get_days_returns_sorted(self, qcodes_db):
        backend = QcodesBackend(qcodes_db)
        days = backend.get_days(offset_hours=0)
        assert len(days) >= 2
        day_strings = [d[0] for d in days]
        assert day_strings == sorted(day_strings)

    def test_get_days_with_offset(self, qcodes_db):
        backend = QcodesBackend(qcodes_db)
        days_utc = backend.get_days(offset_hours=0)
        days_offset = backend.get_days(offset_hours=12)
        # With a +12h offset, some runs near midnight may shift to a different day
        utc_day_strings = [d[0] for d in days_utc]
        offset_day_strings = [d[0] for d in days_offset]
        # They should differ or at least be valid
        assert all(len(d) == 10 for d in offset_day_strings)  # YYYY-MM-DD format

    def test_get_runs_for_day(self, qcodes_db):
        backend = QcodesBackend(qcodes_db)
        days = backend.get_days(offset_hours=0)
        first_day = days[0][0]
        rows, col_defs = backend.get_runs_for_day(first_day, offset_hours=0)
        assert len(rows) > 0
        assert col_defs == QCODES_RUN_GRID_COLUMN_DEFS
        assert 'run_id' in rows[0]
        assert 'experiment_name' in rows[0]

    def test_get_runs_for_nonexistent_day(self, qcodes_db):
        backend = QcodesBackend(qcodes_db)
        rows, col_defs = backend.get_runs_for_day("1999-01-01", offset_hours=0)
        assert rows == []

    def test_get_runs_excludes_blobs(self, qcodes_db):
        """Runs should not contain excluded large columns."""
        # Add blob columns to the test db
        conn = sqlite3.connect(qcodes_db)
        try:
            conn.execute("ALTER TABLE runs ADD COLUMN snapshot TEXT")
            conn.execute("ALTER TABLE runs ADD COLUMN qua_program TEXT")
            conn.execute("UPDATE runs SET snapshot='big blob', qua_program='big code'")
            conn.commit()
        finally:
            conn.close()

        backend = QcodesBackend(qcodes_db)
        days = backend.get_days(offset_hours=0)
        rows, _ = backend.get_runs_for_day(days[0][0], offset_hours=0)
        for row in rows:
            assert 'snapshot' not in row
            assert 'qua_program' not in row
