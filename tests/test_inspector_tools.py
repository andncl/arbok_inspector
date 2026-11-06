"""Tests for the analysis helpers: ridge readout, colour range, export, snapshot."""
import copy
import io
import json
import importlib.resources as resources

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from arbok_inspector.analysis.prepare_data import compute_decay_spectrum, compute_fft
from arbok_inspector.analysis.ridge import ridge_csv, ridge_line, spectrum_dim_of
from arbok_inspector.helpers.figure_builder import PlotSettings, build_figures
from arbok_inspector.helpers.snapshot import flatten_snapshot
from tests.test_decay_spectrum import TAUS, decay_run  # noqa: F401  (fixture)


@pytest.fixture
def settings():
    def load(name):
        with resources.files("arbok_inspector.configurations").joinpath(name).open("r") as f:
            return json.load(f)
    return PlotSettings(plot_dict_1d=load("1d_plot.json"), plot_dict_2d=load("2d_plot.json"))


def with_settings(settings, **changes):
    return PlotSettings(**{**settings.__dict__, **changes})


def figures_for(run, settings):
    view = run.snapshot_view()
    return build_figures(run.compute_subset(view), view, settings).figures


# ─── Ridge readout ───────────────────────────────────────────────────────

class TestRidgeLine:

    def test_position_of_maximum_per_row(self):
        data = xr.DataArray(
            [[0, 5, 1], [7, 0, 0], [0, 1, 9]], dims=["voltage", "f"],
            coords={"voltage": [0.0, 0.5, 1.0],
                    "f": xr.Variable("f", [10.0, 20.0, 30.0], attrs={"units": "Hz"})})
        ridge = ridge_line(data, "f")
        assert ridge.dims == ("voltage",)
        np.testing.assert_array_equal(ridge.values, [20.0, 10.0, 30.0])
        assert ridge.attrs["units"] == "Hz"

    def test_works_along_first_axis(self):
        data = xr.DataArray([[0, 9], [5, 0]], dims=["f", "v"], coords={"f": [1.0, 2.0]})
        np.testing.assert_array_equal(ridge_line(data, "f").values, [2.0, 1.0])

    def test_nan_handling(self):
        data = xr.DataArray(
            [[np.nan, 2, 1], [np.nan] * 3], dims=["v", "f"], coords={"f": [1.0, 2.0, 3.0]})
        ridge = ridge_line(data, "f").values
        assert ridge[0] == 2.0 and np.isnan(ridge[1])

    def test_1d_gives_scalar(self):
        data = xr.DataArray([1, 3, 2], dims=["f"], coords={"f": [1.0, 2.0, 3.0]})
        assert float(ridge_line(data, "f")) == 2.0


class TestSpectrumDim:

    def test_fft_records_its_output_dim(self):
        data = xr.DataArray(np.random.default_rng(0).random((4, 16)), dims=["v", "t"],
                            coords={"t": np.arange(16.0)})
        assert spectrum_dim_of(compute_fft(data, "t")) == "frequency"

    def test_fft_records_renamed_dim(self):
        data = xr.DataArray(np.random.default_rng(0).random((3, 16)), dims=["frequency", "t"],
                            coords={"frequency": [1.0, 2.0, 3.0], "t": np.arange(16.0)})
        assert spectrum_dim_of(compute_fft(data, "t")) == "fft_frequency"

    def test_decay_records_its_output_dim(self):
        t = np.linspace(0, 1, 50)
        data = xr.DataArray(np.exp(-t / 0.1), dims=["t"], coords={"t": t})
        assert spectrum_dim_of(compute_decay_spectrum(data, "t")) == "decay_time"

    def test_plain_data_has_none(self):
        assert spectrum_dim_of(xr.DataArray([1, 2], dims=["x"])) is None

    def test_survives_selection(self, decay_run):
        spectrum = decay_run.compute_subset(decay_run.snapshot_view())["readout__I"]
        assert spectrum_dim_of(spectrum) == "decay_time"
        assert spectrum_dim_of(spectrum.isel(voltage=1)) == "decay_time"


class TestRidgeCsv:

    def test_decay_times_per_voltage(self, decay_run):
        decay_run.compute_subset(decay_run.snapshot_view())
        frame = pd.read_csv(io.StringIO(ridge_csv(decay_run.last_subset)))
        assert list(frame.columns) == ["voltage", "readout.I peak decay_time (s)"]
        np.testing.assert_allclose(frame["readout.I peak decay_time (s)"], TAUS, rtol=0.1)

    def test_single_spectrum_gives_one_row(self, decay_run):
        decay_run.update_subset_dims(decay_run.dim_axis_option['y-axis'], 'select_value', 2)
        decay_run.compute_subset(decay_run.snapshot_view())
        frame = pd.read_csv(io.StringIO(ridge_csv(decay_run.last_subset)))
        assert len(frame) == 1
        assert frame.iloc[0, 0] == pytest.approx(TAUS[2], rel=0.1)

    def test_none_without_spectrum(self, run_3d):
        run_3d.compute_subset(run_3d.snapshot_view())
        assert ridge_csv(run_3d.last_subset) is None


class TestRidgeOverlay:

    def test_ridge_trace_follows_decay_times(self, decay_run, settings):
        [figure] = figures_for(decay_run, with_settings(settings, show_ridge=True))
        heatmap, ridge = figure["data"]
        assert ridge["name"] == "ridge"
        # decay_time is on x, voltage on y → ridge x are decay times per voltage
        np.testing.assert_allclose(ridge["x"], TAUS, rtol=0.1)
        np.testing.assert_allclose(ridge["y"], [0.0, 0.5, 1.0])

    def test_ridge_orientation_with_spectrum_on_y(self, decay_run, settings):
        voltage = decay_run.dim_axis_option['y-axis']
        decay_run.update_subset_dims(voltage, 'x-axis')
        [figure] = figures_for(decay_run, with_settings(settings, show_ridge=True))
        ridge = figure["data"][1]
        np.testing.assert_allclose(ridge["x"], [0.0, 0.5, 1.0])
        np.testing.assert_allclose(ridge["y"], TAUS, rtol=0.1)

    def test_no_ridge_when_switched_off(self, decay_run, settings):
        [figure] = figures_for(decay_run, settings)
        assert len(figure["data"]) == 1

    def test_no_ridge_without_spectrum(self, run_3d, settings):
        [figure] = figures_for(run_3d, with_settings(settings, show_ridge=True))
        assert len(figure["data"]) == 1

    def test_ridge_not_in_json_editor_copy(self, decay_run, settings):
        view = decay_run.snapshot_view()
        bundle = build_figures(
            decay_run.compute_subset(view), view, with_settings(settings, show_ridge=True))
        assert len(bundle.last_figure_2d["data"]) == 1


# ─── Colour range ────────────────────────────────────────────────────────

class TestColorRange:

    @pytest.fixture
    def heatmap(self, run_3d, settings):
        run_3d.plot_selection = ["readout__I"]

        def build(**changes):
            view = run_3d.snapshot_view()
            bundle = build_figures(
                run_3d.compute_subset(view), view, with_settings(settings, **changes))
            return bundle.figures[0]["data"][0], bundle
        return build

    def test_auto_leaves_range_to_plotly(self, heatmap):
        trace, _ = heatmap()
        assert trace.get("zmin") is None and "zauto" not in trace

    def test_percentile_clipping(self, heatmap):
        trace, _ = heatmap(z_range_mode="percentile")
        z = trace["z"]
        np.testing.assert_allclose(
            [trace["zmin"], trace["zmax"]], np.percentile(z, [1, 99]), rtol=1e-5)
        assert trace["zauto"] is False

    def test_manual_range(self, heatmap):
        trace, _ = heatmap(z_range_mode="manual", z_min=-0.5, z_max=0.5)
        assert (trace["zmin"], trace["zmax"]) == (-0.5, 0.5)

    def test_manual_missing_bound_uses_data_extreme(self, heatmap):
        trace, _ = heatmap(z_range_mode="manual", z_min=None, z_max=0.5)
        assert trace["zmin"] == pytest.approx(float(np.nanmin(trace["z"])))
        assert trace["zmax"] == 0.5

    def test_manual_range_in_log_space(self, heatmap):
        trace, _ = heatmap(log_z=True, z_range_mode="manual", z_min=0.01, z_max=1.0)
        assert (trace["zmin"], trace["zmax"]) == pytest.approx((-2.0, 0.0))

    def test_inverted_range_is_ignored(self, heatmap):
        trace, _ = heatmap(z_range_mode="manual", z_min=1.0, z_max=-1.0)
        assert "zauto" not in trace

    def test_range_not_in_json_editor_copy(self, heatmap):
        _, bundle = heatmap(z_range_mode="manual", z_min=-0.5, z_max=0.5)
        assert bundle.last_figure_2d["data"][0].get("zmin") is None


# ─── Image export ────────────────────────────────────────────────────────

class TestExportConfig:

    def test_svg_default_with_file_name(self, run_3d, settings):
        run_3d.plot_selection = ["readout__I"]
        [figure] = figures_for(run_3d, with_settings(settings, export_filename="run7"))
        options = figure["config"]["toImageButtonOptions"]
        assert options == {"format": "svg", "filename": "run7_readout.I"}

    def test_png_gets_high_resolution(self, run_3d, settings):
        [figure] = figures_for(run_3d, with_settings(settings, export_format="png"))
        options = figure["config"]["toImageButtonOptions"]
        assert options["format"] == "png" and options["scale"] == 2

    def test_line_plot_file_name(self, run_3d, settings):
        run_3d.update_subset_dims(run_3d.dim_axis_option['y-axis'], 'select_value')
        [figure] = figures_for(run_3d, with_settings(settings, export_filename="run7"))
        assert figure["config"]["toImageButtonOptions"]["filename"] == "run7_lines"

    def test_template_config_is_kept(self, run_3d, settings):
        template = copy.deepcopy(settings.plot_dict_2d)
        template["config"] = {"displaylogo": False}
        [figure] = figures_for(run_3d, with_settings(settings, plot_dict_2d=template))
        assert figure["config"]["displaylogo"] is False
        assert "toImageButtonOptions" in figure["config"]

    def test_config_not_in_json_editor_copy(self, run_3d, settings):
        view = run_3d.snapshot_view()
        bundle = build_figures(run_3d.compute_subset(view), view, settings)
        assert "config" not in bundle.last_figure_2d


# ─── Instrument snapshot ─────────────────────────────────────────────────

QCODES_LIKE_SNAPSHOT = {
    "station": {
        "instruments": {
            "magnet": {
                "name": "magnet",
                "parameters": {
                    "field": {"__class__": "qcodes.Parameter", "full_name": "magnet_field",
                              "value": 1.5, "unit": "T", "raw_value": 1.5},
                    "IDN": {"__class__": "qcodes.Parameter", "full_name": "magnet_IDN",
                            "value": {"vendor": "ACME"}, "unit": ""},
                },
                "submodules": {
                    "ch1": {"parameters": {"ramp": {"value": 0.1, "unit": "T/s",
                                                    "__class__": "qcodes.Parameter"}}},
                },
            },
        },
        "parameters": {"temperature": {"value": 0.01, "unit": "K", "__class__": "x"}},
        "config": {"core": {"db_location": "x.db"}},
    },
}


class TestFlattenSnapshot:

    def test_rows_for_all_parameters(self):
        rows = {r["name"]: r for r in flatten_snapshot(QCODES_LIKE_SNAPSHOT)}
        assert rows["magnet_field"] == {"name": "magnet_field", "value": "1.5", "unit": "T"}
        assert rows["temperature"]["unit"] == "K"
        assert rows["magnet.ch1.ramp"]["value"] == "0.1"
        assert set(rows) == {"magnet_field", "magnet_IDN", "magnet.ch1.ramp", "temperature"}

    def test_long_values_are_truncated(self):
        snapshot = {"p": {"value": "x" * 1000, "unit": ""}}
        assert flatten_snapshot(snapshot)[0]["value"].endswith("…")

    def test_empty_or_missing(self):
        assert flatten_snapshot(None) == []
        assert flatten_snapshot({}) == []
