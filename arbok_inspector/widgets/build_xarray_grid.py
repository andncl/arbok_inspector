"""Module to build a grid of xarray plots for a given run."""
from __future__ import annotations
from typing import TYPE_CHECKING

import math
import copy
from pathlib import Path
import plotly.graph_objects as go
from nicegui import ui, app

from arbok_inspector.helpers.string_formaters import (
    title_formater, axis_label_formater
)

if TYPE_CHECKING:
    from arbok_inspector.classes.base_run import BaseRun
    from plotly.graph_objs import Figure
    from xarray import DataArray

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
    for result, axes in run.result_axes.items():
        if len(axes['x-axis']) == 0:
            ui.notify(
                'Please select at least one dimension for the x-axis of "' + str(result) + '" to display plots.<br>',
                color = 'red')
            return
    results_1d = {}
    results_2d = {}
    results_unshowable = {}
    for i, result_name in enumerate(run.plot_selection):
        # has_new_data only needs to prime the averaged-subset cache once;
        # subsequent calls reuse the cache automatically.
        result = run.generate_subset_for_result(
            result_name, has_new_data=(has_new_data and i == 0)
        )
        axes = run.result_axes.get(result_name, {})
        assert len(axes['x-axis']) == 1
        x_dim = axes['x-axis'][0]  # only ever one entry!
        y_dim = axes['y-axis'][0] if axes['y-axis'] else None
        result_dims = set(result.dims)
        has_x = x_dim is not None and x_dim.name in result_dims
        has_y = y_dim is not None and y_dim.name in result_dims
        if has_x and has_y and len(result.dims) == 2:
            results_2d[result_name] = result
        elif has_x and len(result.dims) == 1:
            results_1d[result_name] = result
        else:
            results_unshowable[result_name] = result

    figures: list = create_1d_plot(run, results_1d)
    figures += create_2d_plots(run, results_2d)
    create_figures_ui_grid(figures, container, run)

def create_1d_plot(run: BaseRun, results_dict: dict[str, DataArray]) -> list[Figure]:
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
    traces = []
    plot_dict = copy.deepcopy(app.storage.tab["plot_dict_1D"])
    for result_name, result in results_dict.items():
        x_dim_obj = run.result_axes[result_name]['x-axis'][0]
        x_dim = x_dim_obj.name if x_dim_obj is not None else None
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
    axes = run.result_axes.get(result_name, {})
    x_dim = axes['x-axis'][0].name
    y_dim = axes['y-axis'][0].name
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
    plot_dict = add_title_to_plot_dict(run, plot_dict, result_name)
    return go.Figure(plot_dict)

def create_figures_ui_grid(figures: list[Figure], container, run: BaseRun) -> None:
    """
    Generates a grid of plotly figures in the given ui container

    Args:
        figures (list): List of plotly figures to display
        container: UI container to display figures in
        run (BaseRun): Run object for measurement
    """
    num_plots = len(figures)
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

def add_title_to_plot_dict(run: BaseRun, plot_dict: dict, result_name: str | None) -> dict:
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
    title_string += f"<b>{result_name}</b><br>"
    title_string += f"{title_formater(run, result_name)}"
    num_lines = title_string.count("<br>") + 1
    plot_dict["layout"].setdefault("margin", {})
    plot_dict["layout"]["title"]["y"] = 0.97
    plot_dict["layout"]["title"]["yanchor"] = "top"
    plot_dict["layout"]["title"]["font"]["size"] = title_font_size
    plot_dict["layout"]["title"]["text"] = title_string
    plot_dict["layout"]["margin"]["t"] = num_lines * 1.3*title_font_size
    return plot_dict
