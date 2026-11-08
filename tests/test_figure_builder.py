"""Tests for the pure Plotly figure builder."""
import copy
import json
import importlib.resources as resources

import numpy as np
import pytest
import xarray as xr
from nicegui import json as nicegui_json

from arbok_inspector.helpers.figure_builder import (
    DATA_KEYS, PlotSettings, build_figures, compute_heatmap_ticks, decimate,
    strip_data, to_plot_array,
)
from arbok_inspector.classes.view_state import ViewState
from arbok_inspector.widgets.build_xarray_grid import compute_figures
from tests.conftest import ConcreteRun, make_dataset_4d


def load_template(name: str) -> dict:
    with resources.files("arbok_inspector.configurations").joinpath(name).open("r") as f:
        return json.load(f)


@pytest.fixture
def settings():
    return PlotSettings(
        plot_dict_1d=load_template("1d_plot.json"),
        plot_dict_2d=load_template("2d_plot.json"),
    )


def serialize(figure: dict) -> dict:
    """Round-trip through NiceGUI's serializer, as when sending to the browser."""
    return json.loads(nicegui_json.dumps(figure))


def heatmaps(bundle):
    return [f for f in bundle.figures if f["data"][0].get("type") == "heatmap"]


class TestBuildFigures:

    def test_2d_result_gives_heatmap(self, run_3d, settings):
        run_3d.plot_selection = ["readout__I"]
        view = run_3d.snapshot_view()
        bundle = build_figures(run_3d.compute_subset(view), view, settings)
        assert len(bundle.figures) == 1
        trace = bundle.figures[0]["data"][0]
        assert trace["type"] == "heatmap"
        # x-axis is 'frequency' (20 points), y-axis 'voltage' (5 points)
        assert trace["z"].shape == (5, 20)
        assert len(trace["x"]) == 20 and len(trace["y"]) == 5

    def test_heatmap_is_transposed_when_axes_swap(self, run_3d, settings):
        old_x = run_3d.dim_axis_option['x-axis']
        run_3d.update_subset_dims(run_3d.dim_axis_option['y-axis'], 'x-axis')
        run_3d.update_subset_dims(old_x, 'y-axis')
        run_3d.plot_selection = ["readout__I"]
        view = run_3d.snapshot_view()
        trace = build_figures(run_3d.compute_subset(view), view, settings).figures[0]["data"][0]
        assert trace["z"].shape == (20, 5)
        assert len(trace["x"]) == 5

    def test_1d_results_share_one_figure(self, run_3d, settings):
        run_3d.update_subset_dims(run_3d.dim_axis_option['y-axis'], 'select_value', 1)
        run_3d.plot_selection = ["readout__I", "readout__Q"]
        view = run_3d.snapshot_view()
        bundle = build_figures(run_3d.compute_subset(view), view, settings)
        assert len(bundle.figures) == 1
        names = {t["name"] for t in bundle.figures[0]["data"]}
        assert names == {"readout.I", "readout.Q"}

    def test_histogram_mode_gives_heatmap_over_current(self, run_3d, settings):
        run_3d.plot_selection = ["readout__I"]
        run_3d.update_subset_dims(run_3d.dim_axis_option['y-axis'], 'average')
        run_3d.show_histogram = True
        view = run_3d.snapshot_view()
        bundle = build_figures(run_3d.compute_subset(view), view, settings)
        fig = bundle.figures[0]
        assert fig["data"][0]["type"] == "heatmap"
        assert "Current" in fig["layout"]["yaxis"]["title"]["text"]

    def test_fft_mode_1d(self, run_3d, settings):
        run_3d.update_subset_dims(run_3d.dim_axis_option['average'][0], 'fft')
        run_3d.update_subset_dims(run_3d.dim_axis_option['y-axis'], 'select_value')
        run_3d.update_subset_dims(run_3d.dim_axis_option['x-axis'], 'select_value')
        view = run_3d.snapshot_view()
        bundle = build_figures(run_3d.compute_subset(view), view, settings)
        assert len(bundle.figures) == 1
        assert bundle.figures[0]["data"][0]["type"] == "scatter"

    def test_missing_x_coordinate_gives_warning(self, settings):
        data = {"signal": xr.DataArray(np.arange(5.0), dims=["point"])}
        view = ViewState(
            avg_dims=(), x_dim="point", y_dim=None, fft_dim=None,
            selection=(), plot_selection=("signal",))
        bundle = build_figures(data, view, settings)
        assert bundle.figures == []
        assert len(bundle.warnings) == 1

    def test_figures_are_serializable_by_nicegui(self, run_4d, settings):
        """Arrays must be contiguous numpy arrays orjson serializes natively."""
        settings = PlotSettings(**{**settings.__dict__, "log_z": True})
        view = run_4d.snapshot_view()
        for figure in build_figures(run_4d.compute_subset(view), view, settings).figures:
            serialized = serialize(figure)
            assert serialized["data"][0]["z"]

    def test_nan_values_serialize_as_null(self, settings):
        ds = make_dataset_4d()
        ds["result_A"][0, 0, 0, :] = np.nan
        run = ConcreteRun(ds)
        run.prepare_run(avg_axis=None)
        view = run.snapshot_view()
        figure = build_figures(run.compute_subset(view), view, settings).figures[0]
        assert None in serialize(figure)["data"][0]["z"][0]

    def test_ui_revision_constant_across_slider_moves(self, run_4d, settings):
        """Same axes → same uirevision, so plotly keeps the user's zoom."""
        view_a = run_4d.snapshot_view()
        run_4d.dim_axis_option['select_value'][0].select_index = 2
        view_b = run_4d.snapshot_view()
        fig_a = build_figures(run_4d.compute_subset(view_a), view_a, settings).figures[0]
        fig_b = build_figures(run_4d.compute_subset(view_b), view_b, settings).figures[0]
        assert fig_a["layout"]["uirevision"] == fig_b["layout"]["uirevision"]
        run_4d.update_subset_dims(run_4d.dim_axis_option['y-axis'], 'x-axis')
        view_c = run_4d.snapshot_view()
        fig_c = build_figures(run_4d.compute_subset(view_c), view_c, settings).figures[0]
        assert fig_c["layout"]["uirevision"] != fig_a["layout"]["uirevision"]

    def test_templates_are_not_mutated(self, run_3d, settings):
        before = copy.deepcopy(settings.plot_dict_2d)
        view = run_3d.snapshot_view()
        build_figures(run_3d.compute_subset(view), view, settings)
        assert settings.plot_dict_2d == before

    def test_last_figures_have_no_data(self, run_3d, settings):
        view = run_3d.snapshot_view()
        bundle = build_figures(run_3d.compute_subset(view), view, settings)
        for trace in bundle.last_figure_2d["data"]:
            assert not set(trace) & set(DATA_KEYS)
        assert "shapes" not in bundle.last_figure_2d["layout"]

    def test_compute_figures_runs_full_pipeline(self, run_4d, settings):
        bundle = compute_figures(run_4d, run_4d.snapshot_view(), settings)
        assert len(bundle.figures) == 1
        assert run_4d.last_subset is not None


class TestHeatmapOptions:

    @pytest.fixture
    def figure_for(self, run_3d):
        run_3d.plot_selection = ["readout__I"]

        def build(settings):
            view = run_3d.snapshot_view()
            return build_figures(run_3d.compute_subset(view), view, settings).figures[0]
        return build

    def test_gridlines_add_shapes_and_tickvals(self, figure_for, settings):
        fig = figure_for(settings)
        assert fig["layout"]["shapes"]
        assert fig["layout"]["xaxis"]["tickvals"]

    def test_no_gridlines(self, figure_for, settings):
        fig = figure_for(PlotSettings(**{**settings.__dict__, "show_gridlines": False}))
        assert "shapes" not in fig["layout"]

    def test_log_z_keeps_original_values_for_hover(self, figure_for, settings):
        fig = figure_for(PlotSettings(**{**settings.__dict__, "log_z": True}))
        trace = fig["data"][0]
        z, original = trace["z"], trace["customdata"]
        positive = original > 0
        np.testing.assert_allclose(z[positive], np.log10(original[positive]), rtol=1e-5)
        assert np.isnan(z[~positive]).all()

    def test_title_contains_header_and_selection(self, figure_for, settings):
        fig = figure_for(PlotSettings(
            **{**settings.__dict__, "title_header": "HEAD<br>", "title_selection": "rep = 1<br>"}))
        text = fig["layout"]["title"]["text"]
        assert text.startswith("HEAD<br><b>readout.I</b>")
        assert text.endswith("rep = 1<br>")

    def test_large_heatmap_is_downsampled(self, settings):
        ds = xr.Dataset(
            {"big": (["y", "x"], np.random.default_rng(0).standard_normal((300, 2500)))},
            coords={"y": np.arange(300.0), "x": np.arange(2500.0)})
        run = ConcreteRun(ds)
        run.prepare_run()
        view = run.snapshot_view()
        settings = PlotSettings(**{**settings.__dict__, "max_heatmap_points": 1000})
        fig = build_figures(run.compute_subset(view), view, settings).figures[0]
        trace = fig["data"][0]
        assert trace["z"].shape == (300, 834)
        assert len(trace["x"]) == 834
        assert "downsampled 300×2500 → 300×834" in fig["layout"]["title"]["text"]


class TestHelpers:

    def test_to_plot_array_numeric_is_contiguous(self):
        arr = to_plot_array(np.arange(12.0).reshape(3, 4).T, np.float32)
        assert arr.flags["C_CONTIGUOUS"] and arr.dtype == np.float32

    def test_to_plot_array_strings_become_list(self):
        assert to_plot_array(np.array(["a", "b"])) == ["a", "b"]

    def test_decimate_leaves_small_data(self):
        da = xr.DataArray(np.zeros((10, 10)), dims=["a", "b"])
        assert decimate(da, 1000) is da

    def test_decimate_strides_long_dims(self):
        da = xr.DataArray(np.zeros((10, 2001)), dims=["a", "b"])
        assert decimate(da, 1000).shape == (10, 667)

    def test_strip_data_does_not_copy_arrays(self):
        figure = {"data": [{"type": "heatmap", "z": np.zeros((5, 5)), "x": [1], "colorscale": "magma"}],
                  "layout": {"title": {"text": "t"}}}
        stripped = strip_data(figure)
        assert stripped["data"] == [{"type": "heatmap", "colorscale": "magma"}]
        stripped["layout"]["title"]["text"] = "changed"
        assert figure["layout"]["title"]["text"] == "t"

    def test_heatmap_ticks_ignore_nan(self):
        ticks = compute_heatmap_ticks(np.array([0.0, np.nan, 1.0, 2.0]))
        assert ticks and all(np.isfinite(ticks))

    def test_heatmap_ticks_non_numeric(self):
        assert compute_heatmap_ticks(np.array(["a", "b"])) == []


class TestTemplateResolution:
    """plotly.js ignores template *names*; they must be sent as full definitions."""

    def test_named_template_is_resolved_for_browser(self, run_3d, settings):
        view = run_3d.snapshot_view()
        bundle = build_figures(run_3d.compute_subset(view), view, settings)
        template = serialize(bundle.figures[0])["layout"]["template"]
        assert isinstance(template, dict)
        assert template["layout"]["paper_bgcolor"] == "rgb(17,17,17)"  # plotly_dark

    def test_1d_template_is_resolved(self, run_3d, settings):
        run_3d.update_subset_dims(run_3d.dim_axis_option['y-axis'], 'select_value')
        view = run_3d.snapshot_view()
        bundle = build_figures(run_3d.compute_subset(view), view, settings)
        assert isinstance(bundle.figures[0]["layout"]["template"], dict)
        assert bundle.last_figure_1d["layout"]["template"] == "plotly_dark"

    def test_json_editor_copy_keeps_template_name(self, run_3d, settings):
        view = run_3d.snapshot_view()
        bundle = build_figures(run_3d.compute_subset(view), view, settings)
        assert bundle.last_figure_2d["layout"]["template"] == "plotly_dark"

    def test_combined_template_names(self, run_3d, settings):
        template_2d = copy.deepcopy(settings.plot_dict_2d)
        template_2d["layout"]["template"] = "plotly_dark+presentation"
        settings = PlotSettings(**{**settings.__dict__, "plot_dict_2d": template_2d})
        view = run_3d.snapshot_view()
        figure = build_figures(run_3d.compute_subset(view), view, settings).figures[0]
        assert isinstance(figure["layout"]["template"], dict)

    def test_unknown_template_name_is_left_untouched(self, run_3d, settings):
        template_2d = copy.deepcopy(settings.plot_dict_2d)
        template_2d["layout"]["template"] = "does_not_exist"
        settings = PlotSettings(**{**settings.__dict__, "plot_dict_2d": template_2d})
        view = run_3d.snapshot_view()
        figure = build_figures(run_3d.compute_subset(view), view, settings).figures[0]
        assert figure["layout"]["template"] == "does_not_exist"


class TestLineTraceTemplate:
    """Style fields of the first 1D template trace apply to all line traces."""

    @pytest.fixture
    def line_run(self, run_3d):
        run_3d.update_subset_dims(run_3d.dim_axis_option['y-axis'], 'select_value')
        run_3d.plot_selection = ["readout__I", "readout__Q"]
        return run_3d

    def build_with_trace_template(self, run, settings, trace_template):
        template_1d = copy.deepcopy(settings.plot_dict_1d)
        template_1d["data"] = [trace_template]
        settings = PlotSettings(**{**settings.__dict__, "plot_dict_1d": template_1d})
        view = run.snapshot_view()
        return build_figures(run.compute_subset(view), view, settings).figures[0]

    def test_line_style_applies_to_all_traces(self, line_run, settings):
        figure = self.build_with_trace_template(line_run, settings, {
            "type": "scatter", "mode": "lines",
            "line": {"width": 5, "color": "orange"}, "opacity": 0.5})
        for trace in figure["data"]:
            assert trace["mode"] == "lines"
            assert trace["line"] == {"width": 5, "color": "orange"}
            assert trace["opacity"] == 0.5

    def test_template_name_and_data_do_not_leak(self, line_run, settings):
        """The editor's copy contains a trace name; it must not rename every trace."""
        figure = self.build_with_trace_template(line_run, settings, {
            "type": "scatter", "name": "readout.I", "x": [0], "y": [0]})
        assert [t["name"] for t in figure["data"]] == ["readout.I", "readout.Q"]
        assert all(len(t["y"]) == 20 for t in figure["data"])

    def test_defaults_without_template_trace(self, line_run, settings):
        figure = self.build_with_trace_template(line_run, settings, {})
        assert figure["data"][0]["type"] == "scatter"
        assert figure["data"][0]["mode"] == "lines+markers"

    def test_template_traces_are_not_shared(self, line_run, settings):
        figure = self.build_with_trace_template(line_run, settings, {"line": {"width": 2}})
        first, second = figure["data"]
        assert first["line"] is not second["line"]


class TestColorscaleResolution:
    """plotly.js only knows a few colorscale names; 'magma' must be sent expanded."""

    def build_2d(self, run, settings, **trace_and_layout):
        template_2d = copy.deepcopy(settings.plot_dict_2d)
        template_2d["data"][0].update(trace_and_layout.get("trace", {}))
        template_2d["layout"].update(trace_and_layout.get("layout", {}))
        settings = PlotSettings(**{**settings.__dict__, "plot_dict_2d": template_2d})
        view = run.snapshot_view()
        return build_figures(run.compute_subset(view), view, settings)

    def test_default_magma_is_expanded(self, run_3d, settings):
        view = run_3d.snapshot_view()
        bundle = build_figures(run_3d.compute_subset(view), view, settings)
        colorscale = serialize(bundle.figures[0])["data"][0]["colorscale"]
        assert colorscale[0] == [0.0, "#000004"]  # magma starts black

    def test_json_editor_copy_keeps_colorscale_name(self, run_3d, settings):
        view = run_3d.snapshot_view()
        bundle = build_figures(run_3d.compute_subset(view), view, settings)
        assert bundle.last_figure_2d["data"][0]["colorscale"] == "magma"

    def test_reversed_name(self, run_3d, settings):
        bundle = self.build_2d(run_3d, settings, trace={"colorscale": "magma_r"})
        assert bundle.figures[0]["data"][0]["colorscale"][0] == [0.0, "#fcfdbf"]

    def test_unknown_name_is_left_untouched(self, run_3d, settings):
        bundle = self.build_2d(run_3d, settings, trace={"colorscale": "not_a_scale"})
        assert bundle.figures[0]["data"][0]["colorscale"] == "not_a_scale"

    def test_explicit_colorscale_list_untouched(self, run_3d, settings):
        explicit = [[0, "black"], [1, "white"]]
        bundle = self.build_2d(run_3d, settings, trace={"colorscale": explicit})
        assert bundle.figures[0]["data"][0]["colorscale"] == explicit

    def test_layout_colorscale_dict(self, run_3d, settings):
        bundle = self.build_2d(
            run_3d, settings, layout={"colorscale": {"sequential": "magma"}})
        assert isinstance(bundle.figures[0]["layout"]["colorscale"]["sequential"], list)

    def test_cached_template_is_not_modified(self, run_3d, settings):
        from arbok_inspector.helpers.figure_builder import _template_definition
        before = copy.deepcopy(_template_definition("plotly_dark"))
        self.build_2d(run_3d, settings, layout={"colorscale": {"sequential": "magma"}})
        assert _template_definition("plotly_dark") == before

    def test_1d_marker_colorscale(self, run_3d, settings):
        run_3d.update_subset_dims(run_3d.dim_axis_option['y-axis'], 'select_value')
        template_1d = copy.deepcopy(settings.plot_dict_1d)
        template_1d["data"][0]["marker"] = {"colorscale": "magma", "size": 6}
        settings = PlotSettings(**{**settings.__dict__, "plot_dict_1d": template_1d})
        view = run_3d.snapshot_view()
        figure = build_figures(run_3d.compute_subset(view), view, settings).figures[0]
        assert isinstance(figure["data"][0]["marker"]["colorscale"], list)


class TestJsonEditorOrder:
    """The JSON editor shows the 'data' section first."""

    def test_last_figure_is_shown_data_first(self, run_3d, settings):
        from arbok_inspector.widgets.json_plot_settings_dialog import data_section_first
        view = run_3d.snapshot_view()
        stripped = build_figures(run_3d.compute_subset(view), view, settings).last_figure_2d
        ordered = data_section_first(stripped)
        assert list(ordered)[0] == "data"
        assert ordered == stripped

    def test_dict_without_data_is_unchanged(self):
        from arbok_inspector.widgets.json_plot_settings_dialog import data_section_first
        assert data_section_first({"layout": {}}) == {"layout": {}}


class TestPlotJsonExport:
    """Figures for the JSON download: as plotted, readable names, loadable by plotly."""

    @pytest.fixture
    def bundle(self, run_3d, settings):
        run_3d.plot_selection = ["readout__I", "readout__Q"]
        settings = PlotSettings(**{**settings.__dict__, "export_filename": "run1",
                                   "show_ridge": True, "z_range_mode": "percentile"})
        view = run_3d.snapshot_view()
        return build_figures(run_3d.compute_subset(view), view, settings)

    def test_one_export_per_plotted_figure(self, bundle):
        assert [name for name, _ in bundle.exports] == ["run1_readout.I", "run1_readout.Q"]

    def test_keeps_readable_names(self, bundle):
        _, figure = bundle.exports[0]
        assert figure["layout"]["template"] == "plotly_dark"
        assert figure["data"][0]["colorscale"] == "magma"

    def test_display_figure_is_still_resolved(self, bundle):
        assert isinstance(bundle.figures[0]["layout"]["template"], dict)
        assert isinstance(bundle.figures[0]["data"][0]["colorscale"], list)

    def test_browser_only_settings_are_dropped(self, bundle):
        _, figure = bundle.exports[0]
        assert "config" not in figure
        assert "uirevision" not in figure["layout"]
        assert "config" in bundle.figures[0]  # still used by the toolbar

    def test_loads_with_plotly_and_matches_plot(self, bundle):
        import plotly.io as pio
        _, figure = bundle.exports[0]
        loaded = pio.from_json(nicegui_json.dumps(figure))
        np.testing.assert_allclose(
            np.asarray(loaded.data[0].z, dtype=float), bundle.figures[0]["data"][0]["z"])
        assert loaded.data[0].zmin == bundle.figures[0]["data"][0]["zmin"]
        assert loaded.layout.template.layout.paper_bgcolor == "rgb(17,17,17)"

    def test_data_arrays_are_shared_not_copied(self, bundle):
        _, figure = bundle.exports[0]
        assert figure["data"][0]["z"] is bundle.figures[0]["data"][0]["z"]

    def test_resolved_figure_does_not_mutate_input(self):
        from arbok_inspector.helpers.figure_builder import resolved_figure
        figure = {"data": [{"type": "heatmap", "colorscale": "magma", "z": np.zeros((2, 2))}],
                  "layout": {"template": "plotly_dark", "colorscale": {"sequential": "magma"}}}
        original = copy.deepcopy(figure)
        resolved_figure(figure)
        assert figure["layout"] == original["layout"]
        assert figure["data"][0]["colorscale"] == "magma"
