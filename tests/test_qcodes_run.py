"""Integration tests against a real (temporary) QCoDeS database."""
import asyncio
import json
import time
import importlib.resources as resources

import numpy as np
import pytest
from nicegui import ui
from nicegui.testing.user_simulation import user_simulation
from qcodes import config as qc_config
from qcodes.dataset import Measurement, initialise_or_create_database_at, new_experiment
from qcodes.parameters import ManualParameter

from arbok_inspector import run_session
from arbok_inspector.classes.qcodes_run import QcodesRun
from arbok_inspector.helpers.figure_builder import PlotSettings
from arbok_inspector.pages import run_view
from arbok_inspector.state import inspector
from arbok_inspector.widgets.build_xarray_grid import compute_figures

SHAPE = {"iteration": 4, "voltage": 6, "frequency": 9}


def load_template(name: str) -> dict:
    with resources.files("arbok_inspector.configurations").joinpath(name).open("r") as f:
        return json.load(f)


def add_run(meas: Measurement, params: dict, offset: float = 0.0) -> int:
    with meas.run() as saver:
        for i in range(SHAPE["iteration"]):
            for v in np.linspace(0, 1, SHAPE["voltage"]):
                for f in np.linspace(1e9, 2e9, SHAPE["frequency"]):
                    saver.add_result(
                        (params["iteration"], i), (params["voltage"], v),
                        (params["frequency"], f),
                        (params["signal"], offset + v + f / 1e9 + 0.01 * i))
        return saver.run_id


@pytest.fixture
def qcodes_db(tmp_path):
    """QCoDeS database with two identical-shape runs (second one offset by 10)."""
    old_location = qc_config["core"]["db_location"]
    db_path = tmp_path / "test.db"
    initialise_or_create_database_at(db_path)
    new_experiment("exp", sample_name="sample")
    params = {
        "iteration": ManualParameter("iteration"),
        "voltage": ManualParameter("voltage", unit="V"),
        "frequency": ManualParameter("frequency", unit="Hz"),
        "signal": ManualParameter("signal", unit="A"),
    }
    meas = Measurement()
    for name in ("iteration", "voltage", "frequency"):
        meas.register_parameter(params[name])
    meas.register_parameter(
        params["signal"], setpoints=(params["iteration"], params["voltage"], params["frequency"]))
    run_ids = (add_run(meas, params), add_run(meas, params, offset=10.0))
    yield db_path, run_ids
    qc_config["core"]["db_location"] = old_location


def test_qcodes_run_loads_and_renders(qcodes_db):
    db_path, (run_id, _) = qcodes_db
    run = QcodesRun(run_id, db_path=db_path)
    run.prepare_run(avg_axis="iteration")
    assert dict(run.full_data_set.sizes) == SHAPE
    settings = PlotSettings(
        plot_dict_1d=load_template("1d_plot.json"),
        plot_dict_2d=load_template("2d_plot.json"))
    bundle = compute_figures(run, run.snapshot_view(), settings)
    [figure] = bundle.figures
    expected = run.full_data_set["signal"].mean("iteration")
    np.testing.assert_allclose(figure["data"][0]["z"], expected.values, rtol=1e-6)


def test_qcodes_reload_picks_up_new_data(qcodes_db):
    db_path, (run_id, _) = qcodes_db
    run = QcodesRun(run_id, db_path=db_path)
    run.prepare_run(avg_axis="iteration")
    version = run._data_version
    run.reload_dataset()
    assert run._data_version == version + 1
    assert dict(run.full_data_set.sizes) == SHAPE


def test_qcodes_run_defaults_to_connected_database(qcodes_db, monkeypatch):
    db_path, (run_id, _) = qcodes_db
    monkeypatch.setattr(inspector, "qcodes_database_path", db_path)
    assert QcodesRun(run_id).db_path == db_path


@pytest.mark.asyncio
async def test_run_page_with_real_qcodes_runs(qcodes_db, monkeypatch):
    """The real run page (incl. create_run) for two QCoDeS runs opened in turn."""
    db_path, run_ids = qcodes_db
    monkeypatch.setattr(inspector, "database_type", "qcodes")
    monkeypatch.setattr(inspector, "qcodes_database_path", db_path)
    monkeypatch.setattr(run_view, "_default_settings", lambda: {
        "plot_font_size": 15, "show_gridlines": True,
        "plot_dict_1D": load_template("1d_plot.json"),
        "plot_dict_2D": load_template("2d_plot.json"),
    })
    sessions = {}

    async def open_tab(user, run_id):
        await user.open(f"/?run_id={run_id}")
        deadline = time.perf_counter() + 10
        while True:
            session = run_session.get_session(user.client)
            if session is not None and session.plot_grid is not None:
                break
            assert time.perf_counter() < deadline
            await asyncio.sleep(0.01)
        await session.plot_grid.wait_idle()
        sessions[run_id] = (user, session)

    async def root(run_id: int):
        await run_view.run_page(str(run_id))

    async with user_simulation(root) as user_a:
        await open_tab(user_a, run_ids[0])
        [plot] = user_a.find(ui.plotly).elements
        z_first = np.asarray(plot.figure["data"][0]["z"])
        session = sessions[run_ids[0]][1]
        assert session.run.run_id == run_ids[0]
        # no avg_axis configured → iteration is a select_value slider at index 0
        assert session.run.dim_axis_option["select_value"][0].name == "iteration"
        np.testing.assert_allclose(
            z_first, session.run.full_data_set["signal"].isel(iteration=0).values,
            rtol=1e-6)

        await open_tab(user_a, run_ids[1])
        _, session_b = sessions[run_ids[1]]
        z_second = np.asarray(user_a.find(ui.plotly).elements.pop().figure["data"][0]["z"])
        np.testing.assert_allclose(z_second, z_first + 10.0, rtol=1e-6)
        assert session_b.run is not session.run
