"""Module to build a grid of xarray plots for a given run."""
from __future__ import annotations
from typing import TYPE_CHECKING

import math
import copy
from pathlib import Path
import plotly.graph_objects as go
from matplotlib.ticker import MaxNLocator
from nicegui import ui, app

from arbok_inspector.helpers.string_formaters import (
    title_formater, axis_label_formater
)

if TYPE_CHECKING:
    from arbok_inspector.classes.base_run import BaseRun
    from plotly.graph_objs import Figure
    from xarray import DataArray

def build_xarray_grid_hide(has_new_data: bool = False) -> None:
    """
    Build a grid of xarray plots for the given run.

    Args:
        has_new_data (bool): Flag indicating if there is new data to plot.
    """
    print("\nBuilding xarray grid of plots")
    run = app.storage.tab["run"]
    container = app.storage.tab["placeholders"]['plots']
    container.clear()
    if run.dim_axis_option['x-axis'] is None:
        ui.notify(
            'Please select at least one dimension for the x-axis to display plots.<br>',
            color = 'red')
        return
    if run.show_histogram:
        ds = run.generate_binned_subset(has_new_data=has_new_data)
    else:
        ds = run.generate_subset(has_new_data=has_new_data)
    results_1d = {}
    results_2d = {}
    results_unshowable = {}
    for result_name in run.plot_selection:
        result = ds[result_name]
        if len(result.dims) == 1:
            if run.show_histogram:
                results_2d[result_name] = result
            else:
                results_1d[result_name] = result
        elif len(result.dims) == 2:
            results_2d[result_name] = result
        else:
            results_unshowable[result_name] = result

    figures: list = create_1d_plot(run, results_1d)
    figures += create_2d_plots(run, results_2d)
    create_figures_ui_grid(figures, container, run)

def build_xarray_grid(has_new_data: bool = False) -> None:
    """
    Build a grid of xarray plots for the given run.

    Args:
        has_new_data (bool): Flag indicating if there is new data to plot.
    """
    print("\nBuilding xarray grid of plots")
    run = app.storage.tab["run"]
    container = app.storage.tab["placeholders"]['plots']
    container.clear()
    if run.dim_axis_option['x-axis'] is None and run.show_histogram is False:
        ui.notify(
            'Please select at least one dimension for the x-axis to display plots.<br>',
            color = 'red')
        return

    figures = []
    results_same_trace = {}
    for result_name in run.plot_selection:
        if run.show_histogram:
            ds = run.generate_binned_subset(has_new_data=has_new_data)
        else:
            ds = run.generate_subset_dict(has_new_data=has_new_data)
        result = ds[result_name]
        if len(result.dims) == 1:
            if run.show_histogram:
                name_short = result_name.split('__')[0]
                if name_short.endswith('diff') or name_short.endswith('state'):
                    figure = create_1d_plot(run, {result_name: result})[0]
                    figures.append(figure)
                else:
                    results_same_trace[result_name] = result
            else:
                results_same_trace[result_name] = result
        elif len(result.dims) == 2:
            figure = create_2d_figure(result_name, result, run)
            figures.append(figure)
    figures += create_1d_plot(run, results_same_trace)
    create_figures_ui_grid(figures, container, run)

def create_1d_plot(run: BaseRun, results_dict: dict[str, DataArray]) -> Figure:
    """
    Creates plotly figure with all 1D traces in it.

    Args:
        run (RunBase): Run that data is taken from
        results_dict (dict): Dict with result names as keys and xarray DataArrays
            as keys

    Returns:
        plotly figure
    """
    print("Creating 1D plot")
    if run.dim_axis_option['x-axis']:
        x_dim = run.dim_axis_option['x-axis'].name
    else:
        x_dim = 'Current'
    traces = []
    plot_dict = copy.deepcopy(app.storage.tab["plot_dict_1D"])
    for result_name, result in results_dict.items():
        if x_dim in result.coords:
            traces.append({
                "type": "scatter",
                "mode": "lines+markers",
                "name": result_name.replace("__", "."),
                "x": result.coords[x_dim].values.tolist(),
                "y": result.values.tolist(),
            })
            plot_dict["layout"]["xaxis"]["title"]["text"] = axis_label_formater(
                result, x_dim)

        else:
            ui.notify(
                f"Result {result_name} does not have coordinates for {x_dim}",
                type = "negative"
            )
    plot_dict["data"] = traces
    plot_dict = add_title_to_plot_dict(run, plot_dict, None)
    apply_font_size(plot_dict)
    apply_axis_scale(plot_dict)
    apply_gridlines(plot_dict)
    if traces:
        return [go.Figure(plot_dict)]
    else:
        return []

def create_2d_plots(
        run: BaseRun, results_dict: dict[str, DataArray]) -> list[Figure]:
    """
    Creates a list with all plotly 2D plots from the given data dict

    Args:
        run (BaseRun): Run object describing measurement
        results_dict (dict): Dict with result names as keys and xarray
            DataArrays as values
    """
    run = app.storage.tab["run"]
    figures_2d = []
    for result_name, result in results_dict.items():
        figure = create_2d_figure(result_name, result, run)
        figures_2d.append(figure)
    return figures_2d

def create_2d_figure(
        result_name: str, result: DataArray, run: BaseRun) -> Figure:
    """
    Creates single 2D plotly figure for the given result

    Args:
        result_name (str): Name of result
        result (DataArray): xarray DataArray to display
        run (BaseRun): Run object of measurement
    """
    print("Creating 2D plot for result:", result_name)
    x_dim = run.dim_axis_option['x-axis'].name
    try:
        y_dim = run.dim_axis_option['y-axis'].name
    except AttributeError:
        y_dim = 'Current'
    plot_dict = copy.deepcopy(app.storage.tab["plot_dict_2D"])
    plot_dict["layout"]["xaxis"]["title"]["text"] = axis_label_formater(
        result, x_dim)
    plot_dict["layout"]["yaxis"]["title"]["text"] = axis_label_formater(
        result, y_dim)
    plot_dict["layout"]["yaxis"]["automargin"] = True
    plot_dict["layout"]["xaxis"]["automargin"] = True
    if result[x_dim].dims[0] != result.dims[1]:
        result = result.transpose()
    plot_dict["data"][0]["z"] = result.values.tolist()
    plot_dict["data"][0]["x"] = result.coords[x_dim].values.tolist()
    plot_dict["data"][0]["y"] = result.coords[y_dim].values.tolist()
    title = result_name.replace("__", ".")
    plot_dict = add_title_to_plot_dict(run, plot_dict, title)
    apply_font_size(plot_dict)
    apply_axis_scale(plot_dict)
    x_data = result.coords[x_dim].values.tolist()
    y_data = result.coords[y_dim].values.tolist()
    show_grid = app.storage.tab.get("show_gridlines", True)
    if show_grid:
        _set_heatmap_tickvals(plot_dict, x_data, y_data)
    fig = go.Figure(plot_dict)
    if show_grid:
        _add_heatmap_gridline_shapes(fig, x_data, y_data)
    return fig

def create_figures_ui_grid(figures: list[Figure], container, run: BaseRun) -> None:
    """
    Generates a grid of plotly figures in the given ui container

    Args:
        figures (list): List of plotly figures to display
        container: UI container to display figures in
        run (BaseRun): Run object for measurement
    """
    num_plots = len(figures)
    print(num_plots, "plots to display")
    print(run.plots_per_column, "plots per column")
    num_columns = int(min([run.plots_per_column, len(figures)]))
    num_rows = math.ceil(num_plots / num_columns)
    plot_idx = 0
    with container:
        with ui.column().classes('w-full h-full'):
            for row in range(num_rows):
                with ui.row().classes('w-full justify-start flex-wrap'):
                    for col in range(num_columns):
                        if plot_idx >= num_plots:
                            break
                        width_percent = 100 / num_columns - 2
                        height_percent = 100 / num_rows - 2
                        with ui.column().style(
                            f"width: {width_percent}%; box-sizing: border-box;"
                            f"height: {height_percent}%; box-sizing: border-box;"
                            ):
                            ui.plotly(figures[plot_idx])\
                                .classes('w-full h-full')\
                                .style(f'min-height: {int(800/num_rows)}px;')
                        plot_idx += 1

def apply_font_size(plot_dict: dict) -> None:
    """Apply the user-configured font size to axis labels, ticks, and legend."""
    size = app.storage.tab.get("plot_font_size", 12)
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

def apply_axis_scale(plot_dict: dict) -> None:
    """Apply log/linear scale to axes based on user toggle."""
    layout = plot_dict["layout"]
    for axis_key, storage_key in (("xaxis", "log_scale_x"), ("yaxis", "log_scale_y")):
        if axis_key in layout:
            log_on = app.storage.tab.get(storage_key, False)
            layout[axis_key]["type"] = "log" if log_on else "linear"

def apply_gridlines(plot_dict: dict) -> None:
    """Toggle gridlines on axes for non-heatmap plots."""
    show = app.storage.tab.get("show_gridlines", False)
    layout = plot_dict["layout"]
    for axis_key in ("xaxis", "yaxis"):
        if axis_key in layout:
            layout[axis_key]["showgrid"] = show


def _pixel_half_width(data: list) -> float:
    """Half the spacing between the first two data points (heatmap pixel width)."""
    if len(data) < 2:
        return 0
    return abs(data[1] - data[0]) / 2


def _compute_heatmap_ticks(data: list) -> list:
    """Compute nice tick positions for a heatmap axis from its data values."""
    if len(data) < 2:
        return list(data)
    lo, hi = min(data), max(data)
    locator = MaxNLocator(nbins='auto', steps=[1, 2, 2.5, 5, 10])
    return [t for t in locator.tick_values(lo, hi) if lo <= t <= hi]


def _set_heatmap_tickvals(
        plot_dict: dict, x_data: list, y_data: list) -> None:
    """Set explicit tickvals on both axes so labels match the gridlines."""
    layout = plot_dict["layout"]
    layout["xaxis"]["tickvals"] = _compute_heatmap_ticks(x_data)
    layout["yaxis"]["tickvals"] = _compute_heatmap_ticks(y_data)


def _add_heatmap_gridline_shapes(
        fig: Figure, x_data: list, y_data: list) -> None:
    """Draw gridline shapes on top of a heatmap at the tick positions."""
    line_style = {"color": "rgba(255,255,255,0.3)", "width": 1}
    x_hw = _pixel_half_width(x_data)
    y_hw = _pixel_half_width(y_data)
    x_lo, x_hi = min(x_data) - x_hw, max(x_data) + x_hw
    y_lo, y_hi = min(y_data) - y_hw, max(y_data) + y_hw
    for t in _compute_heatmap_ticks(x_data):
        fig.add_shape(
            type="line", xref="x", yref="y",
            x0=t, x1=t, y0=y_lo, y1=y_hi, line=line_style)
    for t in _compute_heatmap_ticks(y_data):
        fig.add_shape(
            type="line", xref="x", yref="y",
            x0=x_lo, x1=x_hi, y0=t, y1=t, line=line_style)

def add_title_to_plot_dict(run: BaseRun, plot_dict: dict, result_name: str) -> dict:
    """
    Generate a title string for the plots based on selected dimensions.

    Args:
        run: The Run object containing the data.
        plot_dict: The plotly figure dictionary to update.
        result_name: The name of the result being plotted.
    Returns:
        dict: The updated plotly figure dictionary with the title.
    """
    title_font_size = 10
    run = app.storage.tab["run"]
    if hasattr(run, 'db_path') and hasattr(run, 'run_id'):
        db_path = Path(run.db_path).resolve()
        title_string = f"Run ID: {run.run_id} -- <i>{db_path}</i><br>"
    else:
        title_string = ""
    if result_name is not None:
        title_string += f"<b>{result_name}</b><br>"
    title_string += f"{title_formater(run)}"
    num_lines = title_string.count("<br>") + 1
    plot_dict["layout"].setdefault("margin", {})
    plot_dict["layout"]["title"]["y"] = 0.97
    plot_dict["layout"]["title"]["yanchor"] = "top"
    plot_dict["layout"]["title"]["font"]["size"] = title_font_size
    plot_dict["layout"]["title"]["text"] = title_string
    plot_dict["layout"]["margin"]["t"] = num_lines * 1.3*title_font_size
    return plot_dict
