"""
Performance regression tests on a large synthetic dataset.

Asserts relative speed (cache hits vs. first computation) and payload sizes
instead of absolute timings, so they are stable across machines.
Run with `-s` to see the timings.
"""
import json
import time
import importlib.resources as resources

import numpy as np
import pytest
import xarray as xr
from nicegui import json as nicegui_json

from arbok_inspector.helpers.figure_builder import PlotSettings
from arbok_inspector.widgets.build_xarray_grid import compute_figures
from tests.conftest import ConcreteRun

pytestmark = pytest.mark.benchmark


def load_template(name: str) -> dict:
    with resources.files("arbok_inspector.configurations").joinpath(name).open("r") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def large_dataset():
    """~8M points per result: iteration x rep x voltage x frequency, 3 results."""
    shape = (20, 10, 101, 401)
    rng = np.random.default_rng(0)
    coords = {
        "iteration": np.arange(shape[0]),
        "rep": np.arange(shape[1]),
        "voltage": np.linspace(0, 1, shape[2]),
        "frequency": np.linspace(1e9, 5e9, shape[3]),
    }
    dims = list(coords)
    return xr.Dataset(
        {name: (dims, rng.standard_normal(shape)) for name in ("I", "Q", "amp")},
        coords=coords)


@pytest.fixture
def settings():
    return PlotSettings(
        plot_dict_1d=load_template("1d_plot.json"),
        plot_dict_2d=load_template("2d_plot.json"),
    )


def timed(func, *args):
    start = time.perf_counter()
    result = func(*args)
    return result, time.perf_counter() - start


def payload_bytes(bundle) -> int:
    return sum(len(nicegui_json.dumps(figure)) for figure in bundle.figures)


def test_slider_step_reuses_averaged_data(large_dataset, settings):
    run = ConcreteRun(large_dataset)
    run.prepare_run(avg_axis="iteration")
    run.plot_selection = ["I"]
    _, first = timed(compute_figures, run, run.snapshot_view(), settings)
    rep = run.dim_axis_option["select_value"][0]
    rep.select_index = 5
    bundle, step = timed(compute_figures, run, run.snapshot_view(), settings)
    print(f"\nfirst render {first*1e3:.0f} ms, slider step {step*1e3:.0f} ms, "
          f"payload {payload_bytes(bundle)/1e6:.2f} MB")
    assert step < first / 3


def test_only_selected_results_are_averaged(large_dataset, settings):
    run = ConcreteRun(large_dataset)
    run.prepare_run(avg_axis="iteration")
    run.plot_selection = ["I"]
    _, one = timed(compute_figures, run, run.snapshot_view(), settings)
    run._invalidate_cache()
    run.plot_selection = ["I", "Q", "amp"]
    _, three = timed(compute_figures, run, run.snapshot_view(), settings)
    print(f"\n1 result {one*1e3:.0f} ms, 3 results {three*1e3:.0f} ms")
    assert one < three / 1.5


def test_histogram_step_reuses_binned_data(large_dataset, settings):
    run = ConcreteRun(large_dataset)
    run.prepare_run(avg_axis="iteration")
    run.plot_selection = ["I"]
    run.update_subset_dims(run.dim_axis_option["y-axis"], "average")
    run.show_histogram = True
    _, first = timed(compute_figures, run, run.snapshot_view(), settings)
    run.dim_axis_option["select_value"][0].select_index = 3
    _, step = timed(compute_figures, run, run.snapshot_view(), settings)
    print(f"\nhistogram first {first*1e3:.0f} ms, slider step {step*1e3:.0f} ms")
    assert step < first / 3


def test_fft_range_change_reuses_fft(large_dataset, settings):
    run = ConcreteRun(large_dataset)
    run.prepare_run(avg_axis="iteration")
    run.plot_selection = ["I"]
    run.update_subset_dims(run.dim_axis_option["x-axis"], "fft")
    run.update_subset_dims(run.dim_axis_option["y-axis"], "x-axis")
    run.fft_freq_range = {"min": 1, "max": 200}
    _, first = timed(compute_figures, run, run.snapshot_view(), settings)
    run.fft_freq_range = {"min": 1, "max": 100}
    _, step = timed(compute_figures, run, run.snapshot_view(), settings)
    print(f"\nfft first {first*1e3:.0f} ms, range change {step*1e3:.0f} ms")
    assert step < first / 3


def test_huge_heatmap_payload_is_capped(settings):
    """A 3000x3000 heatmap must not ship 9M values to the browser."""
    ds = xr.Dataset(
        {"big": (["y", "x"], np.random.default_rng(0).standard_normal((3000, 3000)))},
        coords={"y": np.arange(3000.0), "x": np.arange(3000.0)})
    run = ConcreteRun(ds)
    run.prepare_run()
    bundle, duration = timed(compute_figures, run, run.snapshot_view(), settings)
    size = payload_bytes(bundle)
    print(f"\n3000x3000 heatmap: {duration*1e3:.0f} ms, payload {size/1e6:.1f} MB")
    assert size < 15e6
