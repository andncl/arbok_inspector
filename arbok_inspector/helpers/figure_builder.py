"""
Pure Plotly figure construction for the run view — no UI imports.

Figures are plain dicts holding contiguous numpy arrays. NiceGUI serializes
those natively (orjson), so neither `.tolist()` nor `go.Figure` validation is
needed. Everything here only reads its arguments and is safe to run in a
worker thread.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

import copy
import math
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
import plotly.io as pio
from plotly.colors import get_colorscale
from plotly.exceptions import PlotlyError
from matplotlib.ticker import MaxNLocator, LogLocator

from arbok_inspector.analysis.ridge import ridge_line, spectrum_dim_of
from arbok_inspector.helpers.string_formaters import axis_label_formater

if TYPE_CHECKING:
    from xarray import DataArray
    from arbok_inspector.classes.view_state import ViewState

DATA_KEYS = ("x", "y", "z", "customdata")
TRACE_SPECIFIC_KEYS = DATA_KEYS + ("name",)
GRIDLINE_STYLE = {"color": "rgba(255,255,255,0.3)", "width": 1}
TITLE_FONT_SIZE = 10
DEFAULT_MAX_HEATMAP_POINTS = 1000
DEFAULT_FONT_SIZE = 15
FONT_SIZE_STEP = 2
Z_RANGE_MODES = ('auto', 'percentile', 'manual')
DEFAULT_Z_PERCENTILES = (1.0, 99.0)
RIDGE_STYLE = {"color": "#00e5ff", "width": 1.5}


@dataclass(frozen=True)
class PlotSettings:
    """User plot settings, captured on the event loop right before a render."""
    plot_dict_1d: dict
    plot_dict_2d: dict
    font_size: int = DEFAULT_FONT_SIZE
    log_x: bool = False
    log_y: bool = False
    log_z: bool = False
    show_gridlines: bool = True
    title_header: str = ""
    title_selection: str = ""
    max_heatmap_points: int = DEFAULT_MAX_HEATMAP_POINTS
    show_ridge: bool = False
    z_range_mode: str = 'auto'
    z_min: float | None = None
    z_max: float | None = None
    z_percentiles: tuple[float, float] = DEFAULT_Z_PERCENTILES
    export_format: str = 'svg'
    export_filename: str = 'plot'


@dataclass
class FigureBundle:
    """Result of one render computation."""
    figures: list[dict] = field(default_factory=list)
    last_figure_1d: dict | None = None
    last_figure_2d: dict | None = None
    warnings: list[str] = field(default_factory=list)


def build_figures(
        data: dict[str, DataArray], view: ViewState, settings: PlotSettings
) -> FigureBundle:
    """
    Build all figures for the plotted results. 2D results get one heatmap
    each; 1D results share a single line plot (in histogram mode, processed
    'diff'/'state' results get their own line plot).

    Args:
        data: Subset data as returned by `BaseRun.compute_subset`
        view: View the data was computed for
        settings: Plot settings snapshot
    """
    bundle = FigureBundle()
    results_same_trace = {}

    def add_1d(results: dict[str, DataArray]) -> None:
        figure, stripped, warnings = create_1d_figure(results, view, settings)
        bundle.warnings.extend(warnings)
        if figure is not None:
            bundle.figures.append(figure)
            bundle.last_figure_1d = stripped

    for result_name in view.plot_selection:
        if result_name not in data:
            continue
        result = data[result_name]
        if result.ndim == 1:
            if view.show_histogram and _is_processed_result(result_name):
                add_1d({result_name: result})
            else:
                results_same_trace[result_name] = result
        elif result.ndim == 2:
            figure, stripped = create_2d_figure(result_name, result, view, settings)
            bundle.figures.append(figure)
            bundle.last_figure_2d = stripped
    if results_same_trace:
        add_1d(results_same_trace)
    return bundle


def _is_processed_result(result_name: str) -> bool:
    name_short = result_name.split('__')[0]
    return name_short.endswith('diff') or name_short.endswith('state')


def create_1d_figure(
        results: dict[str, DataArray], view: ViewState, settings: PlotSettings
) -> tuple[dict | None, dict | None, list[str]]:
    """
    Create one line plot with a trace per 1D result.

    Returns:
        (figure, figure without data arrays, warnings); figure is None if no
        result could be plotted
    """
    if (view.fft_dim or view.decay_dim) and not view.x_dim:
        x_dim = None  # use the single dim of each result
    elif view.x_dim:
        x_dim = view.x_dim
    else:
        x_dim = 'Current'
    plot_dict = _template_copy(settings.plot_dict_1d)
    trace_template = (settings.plot_dict_1d.get("data") or [{}])[0]
    traces = []
    warnings = []
    for result_name, result in results.items():
        effective_x = x_dim if x_dim else result.dims[0]
        if effective_x not in result.coords:
            warnings.append(
                f"Result {result_name} does not have coordinates for {effective_x}")
            continue
        # All style fields of the first template trace (line, marker, mode, ...)
        # apply to every trace; data arrays and the name are per result.
        trace = {"type": "scatter", "mode": "lines+markers"}
        trace.update(copy.deepcopy({
            key: value for key, value in trace_template.items()
            if key not in TRACE_SPECIFIC_KEYS}))
        trace["name"] = result_name.replace("__", ".")
        trace["x"] = to_plot_array(result.coords[effective_x].values)
        trace["y"] = to_plot_array(result.values)
        traces.append(trace)
        _set_axis_title(plot_dict, "xaxis", axis_label_formater(result, effective_x))
    if not traces:
        return None, None, warnings
    plot_dict["data"] = traces
    _apply_title(plot_dict, settings, None)
    apply_font_size(plot_dict, settings.font_size)
    apply_axis_scale(plot_dict, settings.log_x, settings.log_y)
    apply_gridlines(plot_dict, settings.show_gridlines)
    stripped = strip_data(plot_dict)
    apply_export_config(plot_dict, settings, "lines")
    plot_dict["layout"]["uirevision"] = _ui_revision(view, settings)
    resolve_template(plot_dict)
    return plot_dict, stripped, warnings


def create_2d_figure(
        result_name: str, result: DataArray, view: ViewState,
        settings: PlotSettings) -> tuple[dict, dict]:
    """
    Create a heatmap for a 2D result.

    Returns:
        (figure, figure without data arrays)
    """
    x_dim = view.x_dim if _is_axis_coord(result, view.x_dim) else result.dims[1]
    x_base = result.coords[x_dim].dims[0] if x_dim in result.coords else x_dim
    if _is_axis_coord(result, view.y_dim) and view.y_dim != x_dim:
        y_dim = view.y_dim
    else:
        y_dim = next((d for d in result.dims if d != x_base), result.dims[0])
    if x_base != result.dims[1]:
        result = result.transpose()
    full_result = result
    full_shape = result.shape
    result = decimate(result, settings.max_heatmap_points)

    plot_dict = _template_copy(settings.plot_dict_2d)
    _set_axis_title(plot_dict, "xaxis", axis_label_formater(result, x_dim))
    _set_axis_title(plot_dict, "yaxis", axis_label_formater(result, y_dim))
    plot_dict["layout"]["yaxis"]["automargin"] = True
    plot_dict["layout"]["xaxis"]["automargin"] = True
    if not plot_dict.get("data"):
        plot_dict["data"] = [{"type": "heatmap"}]
    x_data = to_plot_array(result.coords[x_dim].values)
    y_data = to_plot_array(result.coords[y_dim].values)
    trace = plot_dict["data"][0]
    trace["z"] = to_plot_array(result.values, np.float32)
    trace["x"] = x_data
    trace["y"] = y_data

    title = f"<b>{result_name.replace('__', '.')}</b>"
    if result.shape != full_shape:
        title += (f" <i>(display downsampled {_shape_str(full_shape)}"
                  f" → {_shape_str(result.shape)})</i>")
    _apply_title(plot_dict, settings, title)
    apply_font_size(plot_dict, settings.font_size)
    apply_axis_scale(plot_dict, settings.log_x, settings.log_y)
    apply_colorscale_log(plot_dict, settings.log_z)
    stripped = strip_data(plot_dict)
    # Applied after strip_data so they never end up in a template via the JSON editor
    apply_color_range(plot_dict, settings)
    if settings.show_gridlines:
        add_heatmap_gridlines(
            plot_dict, x_data, y_data, settings.log_x, settings.log_y)
    if settings.show_ridge:
        add_ridge_trace(plot_dict, full_result, x_dim, y_dim)
    apply_export_config(plot_dict, settings, result_name.replace("__", "."))
    plot_dict["layout"]["uirevision"] = _ui_revision(view, settings)
    resolve_template(plot_dict)
    return plot_dict, stripped


def add_ridge_trace(
        plot_dict: dict, result: DataArray, x_dim: str, y_dim: str) -> None:
    """Overlay the brightest point along the spectrum axis (FFT / decay only)."""
    dim = spectrum_dim_of(result)
    if dim is None:
        return
    ridge = to_plot_array(ridge_line(result, dim).values)
    y_base = result.coords[y_dim].dims[0] if y_dim in result.coords else y_dim
    if dim == y_base:
        x, y = to_plot_array(result.coords[x_dim].values), ridge
    else:
        x, y = ridge, to_plot_array(result.coords[y_dim].values)
    plot_dict["data"].append({
        "type": "scatter", "mode": "lines+markers", "name": "ridge",
        "x": x, "y": y, "line": dict(RIDGE_STYLE),
        "marker": {"size": 4, "color": RIDGE_STYLE["color"]},
        "showlegend": False,
    })


def apply_color_range(plot_dict: dict, settings: PlotSettings) -> None:
    """
    Set the heatmap colour range: 'percentile' clips at `z_percentiles`,
    'manual' uses `z_min`/`z_max` (in data units; a missing bound stays at the
    data extreme). With log z the range is applied in log space.
    """
    if settings.z_range_mode == 'auto':
        return
    trace = plot_dict["data"][0]
    z = _numeric(trace.get("z"))
    if z is None:
        return
    finite = z[np.isfinite(z)]
    if finite.size == 0:
        return
    if settings.z_range_mode == 'percentile':
        lo, hi = np.percentile(finite, settings.z_percentiles)
    else:
        lo = _color_value(settings.z_min, settings.log_z)
        hi = _color_value(settings.z_max, settings.log_z)
        lo = finite.min() if lo is None else lo
        hi = finite.max() if hi is None else hi
    if not lo < hi:
        return
    trace["zmin"], trace["zmax"], trace["zauto"] = float(lo), float(hi), False


def _color_value(value: float | None, log_z: bool) -> float | None:
    if value is None:
        return None
    if log_z:
        return math.log10(value) if value > 0 else None
    return float(value)


def apply_export_config(plot_dict: dict, settings: PlotSettings, name: str) -> None:
    """Format and file name of the plot toolbar's download button."""
    config = plot_dict.setdefault("config", {})
    options = dict(config.get("toImageButtonOptions") or {})
    options["format"] = settings.export_format
    options["filename"] = f"{settings.export_filename}_{name}".replace("/", "_")
    if settings.export_format == 'png':
        options.setdefault("scale", 2)
    config["toImageButtonOptions"] = options


def resolve_template(plot_dict: dict) -> None:
    """
    Replace plotly.py names that plotly.js does not know with their definitions:
    the template (e.g. "plotly_dark") and colorscales (e.g. "magma", "magma_r").

    plotly.js has no named templates and only a few named colorscales; unknown
    names are silently replaced by its defaults. `go.Figure` used to expand
    them. Done after `strip_data`, so the copy shown in the JSON editor keeps
    the readable names. Unknown names are left as is.
    """
    template = plot_dict["layout"].get("template")
    if isinstance(template, str):
        resolved = _template_definition(template)
        if resolved is not None:
            plot_dict["layout"]["template"] = resolved
    _resolve_colorscales(plot_dict)


def _resolve_colorscales(node) -> None:
    """
    Expand colorscale names in a nested figure dict: `colorscale: "magma"` on
    traces/markers/coloraxes and `layout.colorscale: {"sequential": "magma"}`.
    Skips data arrays and the (already resolved, shared) template.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key in DATA_KEYS or key == "template":
                continue
            if key == "colorscale" and isinstance(value, str):
                node[key] = _colorscale_definition(value) or value
            elif key == "colorscale" and isinstance(value, dict):
                for kind, name in value.items():
                    if isinstance(name, str):
                        value[kind] = _colorscale_definition(name) or name
            else:
                _resolve_colorscales(value)
    elif isinstance(node, list):
        for item in node:
            _resolve_colorscales(item)


@lru_cache(maxsize=64)
def _colorscale_definition(name: str) -> list | None:
    try:
        return get_colorscale(name)
    except PlotlyError:
        return None


@lru_cache(maxsize=16)
def _template_definition(name: str) -> dict | None:
    try:
        return pio.templates[name].to_plotly_json()
    except (KeyError, ValueError):
        return None


def _is_axis_coord(result: DataArray, name: str | None) -> bool:
    """True if `name` is a 1D coordinate along one of the result's dims."""
    if name is None or name not in result.coords:
        return False
    coord = result.coords[name]
    return coord.ndim == 1 and coord.dims[0] in result.dims


def _shape_str(shape: tuple[int, ...]) -> str:
    return "×".join(str(n) for n in shape)


def _ui_revision(view: ViewState, settings: PlotSettings) -> str:
    """
    Plotly keeps user zoom/pan across updates while this value is unchanged,
    so scrubbing a slider keeps the zoom; changing axes resets it.
    """
    return "|".join(str(v) for v in (
        view.x_dim, view.y_dim, view.fft_dim, view.decay_dim, view.show_histogram,
        settings.log_x, settings.log_y))


def decimate(result: DataArray, max_points: int | None) -> DataArray:
    """Stride-decimate every dim longer than `max_points` (display only)."""
    if not max_points:
        return result
    steps = {
        dim: math.ceil(size / max_points)
        for dim, size in result.sizes.items() if size > max_points}
    if not steps:
        return result
    return result.isel({dim: slice(None, None, step) for dim, step in steps.items()})


def to_plot_array(values, dtype=np.float64):
    """
    Contiguous numeric array that orjson serializes without conversion;
    non-numeric values (strings, dates) fall back to a list.
    """
    values = np.asarray(values)
    if values.dtype.kind in 'biuf':
        return np.ascontiguousarray(values, dtype=dtype)
    return values.tolist()


def _numeric(values) -> np.ndarray | None:
    """Values as float array, or None if they are not numeric."""
    if values is None:
        return None
    values = np.asarray(values)
    if values.dtype.kind not in 'biuf':
        return None
    return values.astype(float, copy=False).ravel()


def strip_data(plot_dict: dict) -> dict:
    """Deep copy of the plot dict without the (large) data arrays."""
    stripped = {
        key: copy.deepcopy(value)
        for key, value in plot_dict.items() if key != "data"}
    stripped["data"] = [
        copy.deepcopy({k: v for k, v in trace.items() if k not in DATA_KEYS})
        for trace in plot_dict.get("data", [])]
    return stripped


def _template_copy(template: dict) -> dict:
    """Copy of a plot template, guaranteed to have layout and axis dicts."""
    plot_dict = strip_data(template)
    layout = plot_dict.setdefault("layout", {})
    for axis_key in ("xaxis", "yaxis"):
        if not isinstance(layout.get(axis_key), dict):
            layout[axis_key] = {}
    return plot_dict


def _set_axis_title(plot_dict: dict, axis_key: str, text: str) -> None:
    axis = plot_dict["layout"][axis_key]
    if not isinstance(axis.get("title"), dict):
        axis["title"] = {}
    axis["title"]["text"] = text


def _apply_title(plot_dict: dict, settings: PlotSettings, result_title: str | None) -> None:
    """Title: run header, result name and the current select_value positions."""
    title_string = settings.title_header
    if result_title is not None:
        title_string += f"{result_title}<br>"
    title_string += settings.title_selection
    num_lines = title_string.count("<br>") + 1
    layout = plot_dict["layout"]
    if not isinstance(layout.get("title"), dict):
        layout["title"] = {}
    title = layout["title"]
    title["y"] = 0.97
    title["yanchor"] = "top"
    title.setdefault("font", {})["size"] = TITLE_FONT_SIZE
    title["text"] = title_string
    layout.setdefault("margin", {})["t"] = num_lines * 1.3 * TITLE_FONT_SIZE


def apply_font_size(plot_dict: dict, size: int) -> None:
    """Apply the font size to axis labels, ticks, legend and colorbars."""
    layout = plot_dict["layout"]
    for axis_key in ("xaxis", "yaxis"):
        if axis_key in layout:
            layout[axis_key].setdefault("title", {}).setdefault("font", {})["size"] = size
            layout[axis_key].setdefault("tickfont", {})["size"] = size
    if "legend" in layout:
        layout["legend"].setdefault("font", {})["size"] = size
    for trace in plot_dict.get("data", []):
        if "colorbar" in trace:
            trace["colorbar"].setdefault("tickfont", {})["size"] = size
            trace["colorbar"].setdefault("title", {}).setdefault("font", {})["size"] = size


def apply_axis_scale(plot_dict: dict, log_x: bool, log_y: bool) -> None:
    """Apply log/linear scale to the x and y axes."""
    layout = plot_dict["layout"]
    for axis_key, log_on in (("xaxis", log_x), ("yaxis", log_y)):
        if axis_key in layout:
            layout[axis_key]["type"] = "log" if log_on else "linear"


def apply_colorscale_log(plot_dict: dict, log_z: bool) -> None:
    """Apply logarithmic color mapping while preserving original z values on hover."""
    if not log_z:
        return
    for trace in plot_dict.get("data", []):
        z = _numeric(trace.get("z"))
        if z is None:
            continue
        z = np.asarray(trace["z"], dtype=float)
        with np.errstate(invalid='ignore'):
            positive = z > 0
        if not positive.any():
            continue
        z_log = np.full(z.shape, np.nan)
        np.log10(z, out=z_log, where=positive)
        trace["customdata"] = to_plot_array(z, np.float32)
        trace["z"] = to_plot_array(z_log, np.float32)
        trace["hovertemplate"] = "x: %{x}<br>y: %{y}<br>z: %{customdata:.4g}<extra></extra>"
        zmin, zmax = float(np.nanmin(z_log)), float(np.nanmax(z_log))
        trace["zmin"] = zmin
        trace["zmax"] = zmax
        tick_exponents = np.arange(math.floor(zmin), math.ceil(zmax) + 1)
        trace.setdefault("colorbar", {})
        trace["colorbar"]["tickvals"] = tick_exponents.tolist()
        trace["colorbar"]["ticktext"] = [
            f"10<sup>{int(e)}</sup>" for e in tick_exponents]


def apply_gridlines(plot_dict: dict, show: bool) -> None:
    """Toggle gridlines on axes and clamp log range when data contains 0."""
    layout = plot_dict["layout"]
    data_key = {"xaxis": "x", "yaxis": "y"}
    for axis_key in ("xaxis", "yaxis"):
        if axis_key not in layout:
            continue
        layout[axis_key]["showgrid"] = show
        if layout[axis_key].get("type") != "log":
            continue
        arrays = [
            _numeric(trace.get(data_key[axis_key]))
            for trace in plot_dict.get("data", [])]
        arrays = [a for a in arrays if a is not None]
        if not arrays:
            continue
        all_vals = np.concatenate(arrays)
        if not (all_vals == 0).any():
            continue
        positives = all_vals[all_vals > 0]
        if positives.size:
            layout[axis_key]["range"] = [
                math.log10(positives.min()), math.log10(positives.max())]


def _pixel_half_width(data: np.ndarray) -> float:
    """Half the spacing between the first two data points (heatmap pixel width)."""
    if len(data) < 2:
        return 0
    return abs(data[1] - data[0]) / 2


def compute_heatmap_ticks(data, log: bool = False) -> list:
    """Compute nice tick positions for a heatmap axis from its data values."""
    data = _numeric(data)
    if data is None:
        return []
    data = data[np.isfinite(data)]
    if len(data) < 2:
        return data.tolist()
    lo, hi = data.min(), data.max()
    if log and lo == 0:
        positives = data[data > 0]
        lo = positives.min() if positives.size else hi
    if log and lo > 0:
        locator = LogLocator(base=10, subs=[1, 2, 5], numticks=12)
    else:
        locator = MaxNLocator(nbins='auto', steps=[1, 2, 2.5, 5, 10])
    return [float(t) for t in locator.tick_values(lo, hi) if lo <= t <= hi]


def add_heatmap_gridlines(
        plot_dict: dict, x_data, y_data, log_x: bool, log_y: bool) -> None:
    """Set tickvals on both axes and draw matching gridline shapes on top."""
    x_values, y_values = _numeric(x_data), _numeric(y_data)
    if x_values is None or y_values is None:
        return
    if not np.isfinite(x_values).any() or not np.isfinite(y_values).any():
        return
    layout = plot_dict["layout"]
    x_ticks = compute_heatmap_ticks(x_values, log=log_x)
    y_ticks = compute_heatmap_ticks(y_values, log=log_y)
    layout["xaxis"]["tickvals"] = x_ticks
    layout["yaxis"]["tickvals"] = y_ticks
    x_hw = _pixel_half_width(x_values)
    y_hw = _pixel_half_width(y_values)
    x_lo, x_hi = float(np.nanmin(x_values) - x_hw), float(np.nanmax(x_values) + x_hw)
    y_lo, y_hi = float(np.nanmin(y_values) - y_hw), float(np.nanmax(y_values) + y_hw)
    shapes = list(layout.get("shapes") or [])
    for t in x_ticks:
        shapes.append({
            "type": "line", "xref": "x", "yref": "y",
            "x0": t, "x1": t, "y0": y_lo, "y1": y_hi, "line": dict(GRIDLINE_STYLE)})
    for t in y_ticks:
        shapes.append({
            "type": "line", "xref": "x", "yref": "y",
            "x0": x_lo, "x1": x_hi, "y0": t, "y1": t, "line": dict(GRIDLINE_STYLE)})
    layout["shapes"] = shapes
