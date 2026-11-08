"""
End-to-end tests of the run page with NiceGUI's simulated user (no browser).

The real `run_page` is shown for a DB-free ConcreteRun; the heavy render step
can be slowed down to reproduce what happens with large datasets.
"""
import asyncio
import json
import threading
import time
import importlib.resources as resources

import numpy as np
import pytest
from nicegui import ui
from nicegui.testing.user_simulation import user_simulation

from arbok_inspector import run_session
from arbok_inspector.pages import run_view
from arbok_inspector.state import inspector
from arbok_inspector.widgets import build_xarray_grid
from tests.conftest import ConcreteRun, make_dataset_3d, make_dataset_4d

pytestmark = pytest.mark.asyncio


def load_template(name: str) -> dict:
    with resources.files("arbok_inspector.configurations").joinpath(name).open("r") as f:
        return json.load(f)


class ComputeProbe:
    """Wraps compute_figures: counts calls, tracks concurrency, adds a delay."""

    def __init__(self, delay: float = 0.0):
        self.delay = delay
        self.calls = 0
        self.running = 0
        self.max_running = 0
        self.lock = threading.Lock()
        self.original = build_xarray_grid.compute_figures

    def __call__(self, run, view, settings):
        with self.lock:
            self.calls += 1
            self.running += 1
            self.max_running = max(self.max_running, self.running)
        try:
            time.sleep(self.delay)  # blocking on purpose: runs in a worker thread
            return self.original(run, view, settings)
        finally:
            with self.lock:
                self.running -= 1


@pytest.fixture
def show_run(monkeypatch):
    """Returns an async context manager opening the run page for a dataset."""
    monkeypatch.setattr(inspector, "database_type", "qcodes")
    monkeypatch.setattr(run_view, "_default_settings", lambda: {
        "plot_font_size": 15, "log_scale_x": False, "log_scale_y": False,
        "log_scale_z": False, "show_gridlines": True,
        "plot_dict_1D": load_template("1d_plot.json"),
        "plot_dict_2D": load_template("2d_plot.json"),
    })

    def factory(dataset, avg_axis="iteration", delay=0.0):
        async def fake_create_run(run_id):
            run = ConcreteRun(dataset, run_id=run_id)
            run.prepare_run(avg_axis=avg_axis)
            return run
        monkeypatch.setattr(run_view, "create_run", fake_create_run)
        probe = ComputeProbe(delay)
        monkeypatch.setattr(build_xarray_grid, "compute_figures", probe)

        async def root():
            await run_view.run_page("1")
        return user_simulation(root), probe
    return factory


async def open_run(user, timeout: float = 5.0):
    """Open the page and wait until the async run page has built its plot grid."""
    await user.open("/")
    deadline = time.perf_counter() + timeout
    session = None
    while session is None or session.plot_grid is None:
        assert time.perf_counter() < deadline, "run page did not finish building"
        await asyncio.sleep(0.01)
        session = run_session.get_session(user.client)
    await session.plot_grid.wait_idle()
    return session


def plots(user):
    return list(user.find(ui.plotly).elements)


async def test_page_renders_initial_plot(show_run):
    simulation, probe = show_run(make_dataset_4d())
    async with simulation as user:
        session = await open_run(user)
        assert probe.calls == 1
        [plot] = plots(user)
        z = plot.figure["data"][0]["z"]
        expected = session.run.full_data_set["result_A"].mean("iteration").isel(rep=0)
        np.testing.assert_allclose(z, expected.values, rtol=1e-6)


async def test_slider_burst_is_coalesced_and_ends_on_latest_value(show_run):
    simulation, probe = show_run(make_dataset_4d(), delay=0.2)
    async with simulation as user:
        session = await open_run(user)
        [slider] = user.find(ui.slider).elements
        [plot_before] = plots(user)
        for value in (1, 2, 3, 2, 3):
            slider.value = value
            await asyncio.sleep(0.01)
        await session.plot_grid.wait_idle()

        # initial render + the one running when the burst started + 1 follow-up
        assert probe.calls <= 3
        assert probe.max_running == 1
        [plot_after] = plots(user)
        assert plot_after is plot_before, "plot should be updated in place"
        expected = session.run.full_data_set["result_A"].mean("iteration").isel(rep=3)
        np.testing.assert_allclose(
            plot_after.figure["data"][0]["z"], expected.values, rtol=1e-6)


async def test_event_loop_stays_responsive_during_slow_render(show_run):
    simulation, _ = show_run(make_dataset_4d(), delay=0.5)
    async with simulation as user:
        session = await open_run(user)
        session.plot_grid.request()
        await asyncio.sleep(0.05)
        assert session.plot_grid.busy
        start = time.perf_counter()
        await asyncio.sleep(0.01)
        assert time.perf_counter() - start < 0.1
        await session.plot_grid.wait_idle()


async def test_plot_selection_change_rebuilds_grid(show_run):
    simulation, _ = show_run(make_dataset_3d())
    async with simulation as user:
        session = await open_run(user)
        assert len(plots(user)) == 1
        user.find("readout.Q").click()
        await session.plot_grid.wait_idle()
        assert len(plots(user)) == 2


async def test_reload_updates_data_and_slider_max(show_run):
    simulation, _ = show_run(make_dataset_4d())
    async with simulation as user:
        session = await open_run(user)
        run = session.run
        bigger = make_dataset_4d().reindex(rep=np.arange(6), fill_value=0.0)
        run._dataset = bigger
        await session.plot_grid.refresh(reload=True)
        [slider] = user.find(ui.slider).elements
        assert slider.props["max"] == 5
        assert run.full_data_set.sizes["rep"] == 6


async def test_no_x_axis_shows_hint_and_clears(show_run):
    simulation, _ = show_run(make_dataset_4d())
    async with simulation as user:
        session = await open_run(user)
        run = session.run
        run.update_subset_dims(run.dim_axis_option["x-axis"], "average")
        await session.plot_grid.refresh()
        await user.should_not_see(ui.plotly)
        await user.should_see("Please select at least one dimension")


async def test_render_error_is_reported_not_raised(show_run, monkeypatch):
    simulation, probe = show_run(make_dataset_4d())
    async with simulation as user:
        session = await open_run(user)

        def broken(*args):
            raise RuntimeError("boom")
        monkeypatch.setattr(build_xarray_grid, "compute_figures", broken)
        await session.plot_grid.refresh()
        await user.should_see("Error while plotting: boom")
        # the grid keeps working afterwards
        monkeypatch.setattr(build_xarray_grid, "compute_figures", probe)
        await session.plot_grid.refresh()
        assert len(plots(user)) == 1


async def test_deleting_client_releases_session(show_run):
    simulation, _ = show_run(make_dataset_4d())
    async with simulation as user:
        session = await open_run(user)
        client = user.client
        assert run_session.get_session(client) is session
        release_handlers = list(client.delete_handlers)
        for handler in release_handlers:
            handler()
        assert run_session.get_session(client) is None
        session.plot_grid.request()
        assert not session.plot_grid.busy, "closed grid must not render anymore"


def select_for(user, dim_name: str):
    """The role dropdown of the given dimension."""
    return next(s for s in user.find(ui.select).elements if s.props.get("label") == dim_name)


async def test_decay_role_from_dropdown(show_run):
    from tests.test_decay_spectrum import make_decay_dataset
    simulation, _ = show_run(make_decay_dataset())
    async with simulation as user:
        session = await open_run(user)
        select_for(user, "time").value = "decay"
        await session.plot_grid.wait_idle()
        [decay_range] = user.find(ui.range).elements
        assert decay_range.props["max"] == 99
        [plot] = plots(user)
        assert "decay_time" in plot.figure["layout"]["xaxis"]["title"]["text"]

        decay_range.value = {"min": 10, "max": 49}
        await session.plot_grid.wait_idle()
        assert len(plot.figure["data"][0]["x"]) == 40


async def test_decay_and_fft_are_mutually_exclusive(show_run):
    from tests.test_decay_spectrum import make_decay_dataset
    simulation, _ = show_run(make_decay_dataset())
    async with simulation as user:
        session = await open_run(user)
        select_for(user, "time").value = "decay"
        await session.plot_grid.wait_idle()
        voltage_select = select_for(user, "voltage")
        voltage_select.value = "fft"
        await user.should_see("Cannot use FFT together with decay")
        await session.plot_grid.wait_idle()
        assert voltage_select.value == "y-axis"
        assert session.run.dim_axis_option["fft"] is None
        assert session.run.dim_axis_option["decay"].name == "time"


async def test_font_size_default_and_step(show_run):
    from arbok_inspector.helpers.figure_builder import DEFAULT_FONT_SIZE, FONT_SIZE_STEP
    simulation, _ = show_run(make_dataset_4d())
    async with simulation as user:
        session = await open_run(user)
        font = next(n for n in user.find(ui.number).elements if n.props.get("label") == "Font")
        assert font.value == DEFAULT_FONT_SIZE == 15
        assert font.props["step"] == FONT_SIZE_STEP == 2
        # browser arrows step from `min`, so the default must lie on that grid
        assert (DEFAULT_FONT_SIZE - font.props["min"]) % FONT_SIZE_STEP == 0
        [plot] = plots(user)
        layout = plot.figure["layout"]
        assert layout["xaxis"]["tickfont"]["size"] == 15
        assert layout["yaxis"]["title"]["font"]["size"] == 15

        font.value = DEFAULT_FONT_SIZE + FONT_SIZE_STEP
        await session.plot_grid.wait_idle()
        assert plot.figure["layout"]["xaxis"]["tickfont"]["size"] == 17


def switch_after_label(user, label: str):
    """The switch in the same actions row as the given label."""
    label_element = next(e for e in user.find(ui.label).elements if e.text == label)
    return next(e for e in label_element.parent_slot.parent if isinstance(e, ui.switch))


async def test_ridge_switch_and_csv_download(show_run):
    from tests.test_decay_spectrum import make_decay_dataset
    simulation, _ = show_run(make_decay_dataset())
    async with simulation as user:
        session = await open_run(user)
        select_for(user, "time").value = "decay"
        await session.plot_grid.wait_idle()
        [plot] = plots(user)
        assert len(plot.figure["data"]) == 1

        switch_after_label(user, "Ridge:").value = True
        await session.plot_grid.wait_idle()
        assert [t.get("name") for t in plot.figure["data"]][1] == "ridge"

        user.find("CSV").click()
        response = await user.download.next()
        assert "readout.I peak decay_time (s)" in response.text


async def test_ridge_csv_without_spectrum_warns(show_run):
    simulation, _ = show_run(make_dataset_4d())
    async with simulation as user:
        await open_run(user)
        user.find("CSV").click()
        await user.should_see("Ridge readout needs an FFT or decay dimension")


async def test_python_button_shows_snippet(show_run):
    simulation, _ = show_run(make_dataset_4d())
    async with simulation as user:
        await open_run(user)
        user.find("Python").click()
        code = next(c for c in user.find(ui.code).elements if "data = {}" in c.content)
        assert "arr.mean(['iteration'])" in code.content
        assert "arr.isel({'rep': 0}).squeeze()" in code.content


async def test_colour_range_controls(show_run):
    simulation, _ = show_run(make_dataset_4d())
    async with simulation as user:
        session = await open_run(user)
        [plot] = plots(user)
        z_toggle = next(t for t in user.find(ui.toggle).elements if "percentile" in t.options)
        z_toggle.value = "manual"
        z_min = next(n for n in user.find(ui.number).elements if n.props.get("label") == "z min")
        z_max = next(n for n in user.find(ui.number).elements if n.props.get("label") == "z max")
        assert z_min.visible
        z_min.value, z_max.value = -0.25, 0.25
        await session.plot_grid.wait_idle()
        trace = plot.figure["data"][0]
        assert (trace["zmin"], trace["zmax"]) == (-0.25, 0.25)
        z_toggle.value = "auto"
        await session.plot_grid.wait_idle()
        assert not z_min.parent_slot.parent.visible
        assert plot.figure["data"][0].get("zauto") is None


async def test_export_format_toggle(show_run):
    simulation, _ = show_run(make_dataset_4d())
    async with simulation as user:
        session = await open_run(user)
        [plot] = plots(user)
        assert plot.figure["config"]["toImageButtonOptions"]["format"] == "svg"
        export_toggle = next(t for t in user.find(ui.toggle).elements if "svg" in t.options)
        export_toggle.value = "png"
        await session.plot_grid.wait_idle()
        assert plot.figure["config"]["toImageButtonOptions"]["format"] == "png"


async def test_snapshot_section_is_searchable(show_run, monkeypatch):
    from tests.test_inspector_tools import QCODES_LIKE_SNAPSHOT
    monkeypatch.setattr(
        ConcreteRun, "get_snapshot", lambda self: QCODES_LIKE_SNAPSHOT, raising=False)
    simulation, _ = show_run(make_dataset_4d())
    async with simulation as user:
        await open_run(user)
        expansion = next(e for e in user.find(ui.expansion).elements
                         if e.props.get("label") == "instrument snapshot")
        expansion.value = True
        [table] = user.find(ui.table).elements
        assert {row["name"] for row in table.rows} >= {"magnet_field", "temperature"}
        search = next(i for i in user.find(ui.input).elements
                      if i.props.get("label") == "Search parameters")
        search.value = "field"
        assert table.filter == "field"
        expansion.value = False
        expansion.value = True
        assert len(user.find(ui.table).elements) == 1, "table must only be built once"


async def test_plot_json_download(show_run):
    import json as std_json
    import plotly.io as pio
    from tests.conftest import make_dataset_3d
    simulation, _ = show_run(make_dataset_3d())
    async with simulation as user:
        session = await open_run(user)
        user.find("readout.Q").click()
        await session.plot_grid.wait_idle()
        user.find("Plot JSON").click()
        deadline = time.perf_counter() + 5
        while len(user.download.http_responses) < 2:
            assert time.perf_counter() < deadline, "expected one JSON file per plot"
            await asyncio.sleep(0.05)
        figures = [std_json.loads(r.text) for r in user.download.http_responses]
        titles = sorted(f["layout"]["title"]["text"] for f in figures)
        assert "<b>readout.I</b>" in titles[0] and "<b>readout.Q</b>" in titles[1]
        assert all(f["layout"]["template"] == "plotly_dark" for f in figures)
        response = user.download.http_responses[0]
        assert pio.from_json(response.text).data[0].type == "heatmap"


async def test_plot_json_without_plots_warns(show_run):
    simulation, _ = show_run(make_dataset_4d())
    async with simulation as user:
        session = await open_run(user)
        run = session.run
        run.update_subset_dims(run.dim_axis_option["x-axis"], "average")
        await session.plot_grid.refresh()
        user.find("Plot JSON").click()
        await user.should_see("Nothing plotted yet")
