"""Tests for the decay-time spectrum (regularised inverse Laplace transform)."""
import numpy as np
import pytest
import xarray as xr

from arbok_inspector.analysis.prepare_data import (
    DECAY_TIME_POINTS, compute_decay_spectrum, decay_time_axis)

TIME = np.linspace(0, 20e-6, 400)


def trace_array(values, time=TIME, units="s"):
    return xr.DataArray(
        values, dims=["time"],
        coords={"time": xr.Variable("time", time, attrs={"units": units})})


def peak_times(spectrum: xr.DataArray, rel_height: float = 0.2) -> list[float]:
    """Decay times of local maxima, strongest first."""
    values = spectrum.values
    taus = spectrum.coords["decay_time"].values
    idx = [i for i in range(1, len(values) - 1)
           if values[i] > values[i - 1] and values[i] >= values[i + 1]
           and values[i] > rel_height * np.nanmax(values)]
    return [taus[i] for i in sorted(idx, key=lambda i: -values[i])]


def decay(tau):
    return np.exp(-TIME / tau)


def assert_peaks(spectrum, expected, rel=0.1):
    found = peak_times(spectrum)
    assert len(found) == len(expected), f"peaks {found} != {expected}"
    for tau in expected:
        assert any(abs(f - tau) / tau < rel for f in found), f"{tau} not in {found}"


class TestPeakPositions:
    """The brightest point sits at the decay time, however the trace starts or ends."""

    @pytest.mark.parametrize("values", [
        pytest.param(decay(2e-6), id="decay 1 to 0"),
        pytest.param(1 - decay(2e-6), id="rise 0 to 1"),
        pytest.param(0.8 - 0.5 * decay(2e-6), id="rise 0.3 to 0.8"),
        pytest.param(-3.0 + 2.0 * decay(2e-6), id="decay -1 to -3"),
    ])
    def test_single_decay_any_baseline(self, values):
        spectrum = compute_decay_spectrum(trace_array(values), "time")
        assert_peaks(spectrum, [2e-6])

    def test_two_decays_are_resolved(self):
        values = 0.5 * decay(1e-6) + 0.5 * decay(4e-6)
        assert_peaks(compute_decay_spectrum(trace_array(values), "time"), [1e-6, 4e-6])

    def test_two_decays_with_offset_and_noise(self):
        rng = np.random.default_rng(3)
        values = 0.5 * decay(1e-6) + 0.5 * decay(4e-6) + 0.2 + 0.02 * rng.standard_normal(TIME.size)
        # Inverse Laplace is ill-conditioned: with noise, decays only 4x apart come
        # out ~10% off (median over seeds), occasionally up to ~30%.
        assert_peaks(compute_decay_spectrum(trace_array(values), "time"), [1e-6, 4e-6], rel=0.3)

    def test_noisy_single_decay(self):
        rng = np.random.default_rng(0)
        values = decay(2e-6) + 0.05 * rng.standard_normal(TIME.size)
        spectrum = compute_decay_spectrum(trace_array(values), "time")
        assert abs(peak_times(spectrum)[0] - 2e-6) / 2e-6 < 0.15

    def test_brightness_scales_with_amplitude(self):
        small = compute_decay_spectrum(trace_array(0.1 * decay(2e-6)), "time")
        large = compute_decay_spectrum(trace_array(1.0 * decay(2e-6)), "time")
        np.testing.assert_allclose(large.max(), 10 * small.max(), rtol=1e-3)

    def test_spectrum_is_non_negative(self):
        spectrum = compute_decay_spectrum(trace_array(1 - decay(2e-6)), "time")
        assert (spectrum.values >= 0).all()


class TestAxisAndUnits:

    def test_decay_time_axis_keeps_units(self):
        spectrum = compute_decay_spectrum(trace_array(decay(2e-6), units="s"), "time")
        assert spectrum.dims == ("decay_time",)
        assert spectrum.coords["decay_time"].attrs["units"] == "s"

    def test_axis_spans_sample_spacing_to_window(self):
        taus = decay_time_axis(TIME)
        assert taus.size == DECAY_TIME_POINTS
        np.testing.assert_allclose([taus[0], taus[-1]], [TIME[1] - TIME[0], TIME[-1]])
        assert np.all(np.diff(np.log(taus)) > 0)

    def test_other_dims_are_kept_in_place(self):
        values = np.stack([decay(tau) for tau in (1e-6, 2e-6, 4e-6)], axis=1)
        da = xr.DataArray(values, dims=["time", "voltage"],
                          coords={"time": TIME, "voltage": [0.0, 0.5, 1.0]})
        spectrum = compute_decay_spectrum(da, "time")
        assert spectrum.dims == ("decay_time", "voltage")
        peaks = spectrum.coords["decay_time"].values[spectrum.argmax("decay_time").values]
        np.testing.assert_allclose(peaks, [1e-6, 2e-6, 4e-6], rtol=0.1)

    def test_name_collision_is_avoided(self):
        da = xr.DataArray(
            np.stack([decay(2e-6)] * 2), dims=["decay_time", "time"],
            coords={"decay_time": [0, 1], "time": TIME})
        spectrum = compute_decay_spectrum(da, "time")
        assert "decay_decay_time" in spectrum.dims


class TestRobustInput:

    def test_trailing_nans_of_incomplete_run(self):
        values = decay(2e-6)
        values[300:] = np.nan
        assert_peaks(compute_decay_spectrum(trace_array(values), "time"), [2e-6])

    def test_all_nan_trace_gives_nan(self):
        spectrum = compute_decay_spectrum(trace_array(np.full(TIME.size, np.nan)), "time")
        assert np.isnan(spectrum.values).all()

    def test_descending_time_axis(self):
        da = trace_array(decay(2e-6)[::-1], time=TIME[::-1])
        assert_peaks(compute_decay_spectrum(da, "time"), [2e-6])

    def test_non_uniform_time_axis(self):
        time = np.sort(np.random.default_rng(0).uniform(0, 20e-6, 300))
        da = trace_array(np.exp(-time / 2e-6), time=time)
        assert_peaks(compute_decay_spectrum(da, "time"), [2e-6])

    def test_missing_dim_raises(self):
        with pytest.raises(ValueError, match="not found"):
            compute_decay_spectrum(trace_array(decay(2e-6)), "nope")

    def test_too_few_points_raises(self):
        da = trace_array([1.0, 0.5], time=np.array([0.0, 1.0]))
        with pytest.raises(ValueError, match="at least 3"):
            compute_decay_spectrum(da, "time")


# ─── Run integration ─────────────────────────────────────────────────────

import json
import importlib.resources as resources

from arbok_inspector.helpers.figure_builder import PlotSettings, build_figures
from arbok_inspector.widgets.build_xarray_grid import compute_figures
from tests.conftest import ConcreteRun

TAUS = np.array([1e-6, 2e-6, 4e-6])


def make_decay_dataset():
    """iteration x voltage x time; the decay time depends on the voltage."""
    rng = np.random.default_rng(0)
    signal = (np.exp(-TIME[None, None, :] / TAUS[None, :, None])
              + 0.01 * rng.standard_normal((5, TAUS.size, TIME.size)))
    return xr.Dataset(
        {"readout__I": (["iteration", "voltage", "time"], signal)},
        coords={
            "iteration": np.arange(5),
            "voltage": xr.Variable("voltage", [0.0, 0.5, 1.0], attrs={"units": "V"}),
            "time": xr.Variable("time", TIME, attrs={"units": "s"}),
        })


@pytest.fixture
def decay_run():
    """Averaged over iteration, voltage on the y-axis, time assigned to 'decay'."""
    run = ConcreteRun(make_decay_dataset())
    run.prepare_run(avg_axis="iteration")
    run.update_subset_dims(run.dim_axis_option['x-axis'], 'decay')
    return run


def count_calls(monkeypatch):
    import arbok_inspector.classes.base_run as base_run_module
    calls = []
    original = base_run_module.compute_decay_spectrum

    def counting(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)
    monkeypatch.setattr(base_run_module, "compute_decay_spectrum", counting)
    return calls


class TestDecayRole:

    def test_decay_role_assignment(self, decay_run):
        assert decay_run.show_decay
        assert decay_run.dim_axis_option['decay'].name == "time"
        assert decay_run.snapshot_view().decay_dim == "time"

    def test_assigning_decay_demotes_previous_holder(self, decay_run):
        voltage = decay_run.dim_axis_option['y-axis']
        decay_run.update_subset_dims(voltage, 'decay')
        assert decay_run.dim_axis_option['decay'] is voltage
        time_dim = next(d for d in decay_run.dims if d.name == "time")
        assert time_dim.option == 'select_value'

    def test_removing_decay_role(self, decay_run):
        decay_run.update_subset_dims(decay_run.dim_axis_option['decay'], 'x-axis')
        assert not decay_run.show_decay

    def test_compute_subset_peaks_per_voltage(self, decay_run):
        spectrum = decay_run.compute_subset(decay_run.snapshot_view())["readout__I"]
        assert set(spectrum.dims) == {"voltage", "decay_time"}
        peaks = spectrum.coords["decay_time"].values[
            spectrum.argmax("decay_time").transpose("voltage").values]
        np.testing.assert_allclose(peaks, TAUS, rtol=0.1)

    def test_range_change_reuses_spectrum(self, decay_run, monkeypatch):
        calls = count_calls(monkeypatch)
        decay_run.compute_subset(decay_run.snapshot_view())
        decay_run.decay_range = {'min': 10, 'max': 59}
        sliced = decay_run.compute_subset(decay_run.snapshot_view())["readout__I"]
        assert len(calls) == 1
        assert sliced.sizes["decay_time"] == 50

    def test_selection_change_reuses_spectrum(self, decay_run, monkeypatch):
        calls = count_calls(monkeypatch)
        decay_run.compute_subset(decay_run.snapshot_view())
        decay_run.update_subset_dims(decay_run.dim_axis_option['y-axis'], 'select_value', 2)
        spectrum = decay_run.compute_subset(decay_run.snapshot_view())["readout__I"]
        assert len(calls) == 1
        assert spectrum.dims == ("decay_time",)

    def test_reload_recomputes_spectrum(self, decay_run, monkeypatch):
        calls = count_calls(monkeypatch)
        decay_run.compute_subset(decay_run.snapshot_view())
        decay_run.reload_dataset()
        decay_run.compute_subset(decay_run.snapshot_view())
        assert len(calls) == 2

    def test_generate_decay_subset_requires_role(self):
        run = ConcreteRun(make_decay_dataset())
        run.prepare_run(avg_axis="iteration")
        with pytest.raises(ValueError, match="No dimension assigned to 'decay'"):
            run.generate_decay_subset()


def load_settings():
    def load(name):
        with resources.files("arbok_inspector.configurations").joinpath(name).open("r") as f:
            return json.load(f)
    return PlotSettings(plot_dict_1d=load("1d_plot.json"), plot_dict_2d=load("2d_plot.json"))


class TestDecayFigures:

    def test_heatmap_has_decay_time_axis_with_units(self, decay_run):
        bundle = compute_figures(decay_run, decay_run.snapshot_view(), load_settings())
        [figure] = bundle.figures
        assert figure["data"][0]["type"] == "heatmap"
        x_title = figure["layout"]["xaxis"]["title"]["text"]
        assert "decay_time" in x_title and "(s)" in x_title

    def test_single_trace_gives_line_plot_over_decay_time(self, decay_run):
        decay_run.update_subset_dims(decay_run.dim_axis_option['y-axis'], 'select_value', 1)
        view = decay_run.snapshot_view()
        bundle = build_figures(decay_run.compute_subset(view), view, load_settings())
        [figure] = bundle.figures
        trace = figure["data"][0]
        assert trace["type"] == "scatter"
        assert abs(trace["x"][np.argmax(trace["y"])] - 2e-6) / 2e-6 < 0.1
