"""Shared test fixtures for arbok_inspector tests."""
import numpy as np
import xarray as xr
import pytest

from arbok_inspector.classes.dim import Dim
from arbok_inspector.classes.base_run import BaseRun


class ConcreteRun(BaseRun):
    """Concrete implementation of BaseRun for testing (no DB needed)."""

    def __init__(self, dataset: xr.Dataset, run_id: int = 1):
        class FakeInspector:
            database_type = 'test'
        super().__init__(run_id, FakeInspector())
        self._dataset = dataset
        self.name = "test_run"

    def _load_dataset(self) -> xr.Dataset:
        return self._dataset

    def _get_database_columns(self) -> dict:
        return {"run_id": {"value": self.run_id}}

    def get_qua_code(self, as_string: bool = False) -> str:
        return "# no qua code"


def make_dataset_3d():
    """Create a 3D dataset: iteration x voltage x frequency with two results."""
    iteration = np.arange(10)
    voltage = np.linspace(0, 1, 5)
    frequency = np.linspace(1e9, 5e9, 20)
    rng = np.random.default_rng(42)
    data_I = rng.standard_normal((10, 5, 20))
    data_Q = rng.standard_normal((10, 5, 20))
    ds = xr.Dataset(
        {
            "readout__I": (["iteration", "voltage", "frequency"], data_I),
            "readout__Q": (["iteration", "voltage", "frequency"], data_Q),
        },
        coords={
            "iteration": iteration,
            "voltage": voltage,
            "frequency": frequency,
        },
    )
    return ds


def make_dataset_2d():
    """Create a 2D dataset: voltage x frequency with one result."""
    voltage = np.linspace(0, 1, 5)
    frequency = np.linspace(1e9, 5e9, 20)
    rng = np.random.default_rng(42)
    data = rng.standard_normal((5, 20))
    ds = xr.Dataset(
        {"signal": (["voltage", "frequency"], data)},
        coords={"voltage": voltage, "frequency": frequency},
    )
    return ds


def make_dataset_1d():
    """Create a 1D dataset: frequency with one result."""
    frequency = np.linspace(1e9, 5e9, 20)
    rng = np.random.default_rng(42)
    data = rng.standard_normal(20)
    ds = xr.Dataset(
        {"signal": (["frequency"], data)},
        coords={"frequency": frequency},
    )
    return ds


def make_dataset_4d():
    """4D dataset: iteration x rep x voltage x frequency."""
    ds = xr.Dataset(
        {
            "result_A": (
                ["iteration", "rep", "voltage", "frequency"],
                np.random.default_rng(42).standard_normal((3, 4, 5, 10)),
            ),
        },
        coords={
            "iteration": np.arange(3),
            "rep": np.arange(4),
            "voltage": np.linspace(0, 1, 5),
            "frequency": np.linspace(1e9, 5e9, 10),
        },
    )
    return ds


@pytest.fixture
def dataset_3d():
    return make_dataset_3d()


@pytest.fixture
def dataset_2d():
    return make_dataset_2d()


@pytest.fixture
def dataset_1d():
    return make_dataset_1d()


@pytest.fixture
def dataset_4d():
    return make_dataset_4d()


@pytest.fixture
def run_3d(dataset_3d):
    run = ConcreteRun(dataset_3d)
    run.prepare_run(avg_axis="iteration", result_keywords="")
    return run


@pytest.fixture
def run_2d(dataset_2d):
    run = ConcreteRun(dataset_2d)
    run.prepare_run(avg_axis=None, result_keywords="")
    return run


@pytest.fixture
def run_1d(dataset_1d):
    run = ConcreteRun(dataset_1d)
    run.prepare_run(avg_axis=None, result_keywords="")
    return run


@pytest.fixture
def run_4d(dataset_4d):
    run = ConcreteRun(dataset_4d)
    run.prepare_run(avg_axis="iteration", result_keywords="")
    return run
