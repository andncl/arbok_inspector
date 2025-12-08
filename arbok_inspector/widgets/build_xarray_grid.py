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
    from arbok_inspector.classes.dim import Dim
    from arbok_inspector.classes.base_run import BaseRun
    from plotly.graph_objs import Figure

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
    if run.dim_axis_option['x-axis'] is None:
        ui.notify(
            'Please select at least one dimension for the x-axis to display plots.<br>',
            color = 'red')
        return
    ds = run.generate_subset(has_new_data=has_new_data)
    if len(ds.dims) == 1:
        create_1d_plot(run, ds, container)
    elif len(ds.dims) == 2:
        create_2d_grid(run, ds, container)
    else:
        ui.notify(
            'The selected dimensions result in more than 2D data.<br>'
            'Please select only 1 or 2 dimensions to plot)',
            color = 'red')

def create_1d_plot(run: BaseRun, ds: xr.Dataset, container: ui.Row) -> None:
    """
    Create a 1D plot for the given run and dataset.

    Args:
        run: The Run object containing the data to plot.
        ds: The xarray Dataset containing the data.
        container: The NiceGUI container to hold the plot.
    """
    print("Creating 1D plot")
    x_dim = run.dim_axis_option['x-axis'].name
    traces = []
    plot_dict = copy.deepcopy(app.storage.tab["plot_dict_1D"])
    for key in run.plot_selection:
        da = ds[key]
        traces.append({
            "type": "scatter",
            "mode": "lines+markers",
            "name": key.replace("__", "."),
            "x": da.coords[x_dim].values.tolist(),
            "y": da.values.tolist(),
        })

    plot_dict["data"] = traces
    plot_dict["layout"]["xaxis"]["title"]["text"] = axis_label_formater(ds, x_dim)
    plot_dict = add_title_to_plot_dict(run, plot_dict, None)

    with container:
        fig = go.Figure(plot_dict)
        run.figures = [fig]
        plot = ui.plotly(fig).classes('flex-1 h-full w-full').style('height:100%; min-height:700px;')
        run.plots = [plot]
        app.storage.tab["plot_dict_1D"] = plot_dict

def create_2d_grid(run: BaseRun, ds, container) -> dict:
    """
    Create a grid of 2D plots for the given run and dataset.

    Args:
        run: The Run object containing the data to plot.
        ds: The xarray Dataset containing the data.
        container: The NiceGUI container to hold the plots.
    """
    print("Creating 2D grid of plots")
    if not all([run.dim_axis_option[axis]is not None for axis in ['x-axis', 'y-axis']]):
        ui.notify(
            'Please select both x-axis and y-axis dimensions to display 2D plots.<br>'
            f'x: {run.dim_axis_option["x-axis"]}<br>'
            f'y: {run.dim_axis_option["y-axis"]}',
            color = 'red')
        return
    keys = run.plot_selection
    num_plots = len(keys)
    num_columns = int(min([run.plots_per_column, len(keys)]))
    num_rows = math.ceil(num_plots / num_columns)
    pretty_keys = [key.replace("__", ".") for key in keys]

    x_dim = run.dim_axis_option['x-axis'].name
    y_dim = run.dim_axis_option['y-axis'].name
    plot_dict = copy.deepcopy(app.storage.tab["plot_dict_2D"])
    plot_dict["layout"]["xaxis"]["title"]["text"] = axis_label_formater(ds, x_dim)
    plot_dict["layout"]["yaxis"]["title"]["text"] = axis_label_formater(ds, y_dim)
    plot_dict["layout"]["yaxis"]["automargin"] = True
    plot_dict["layout"]["xaxis"]["automargin"] = True
    plot_idx = 0
    def create_2d_plot(plot_dict, plot_idx):
        key = keys[plot_idx]
        da = ds[key]
        if da[x_dim].dims[0] != da.dims[1]:
            # TODO: CHECK THIS!
            da = da.transpose() #y_dim, x_dim)
        plot_dict["data"][0]["z"] = da.values.tolist()
        plot_dict["data"][0]["x"] = da.coords[x_dim].values.tolist()
        plot_dict["data"][0]["y"] = da.coords[y_dim].values.tolist()
        plot_dict = add_title_to_plot_dict(run, plot_dict, pretty_keys[plot_idx])

        return go.Figure(plot_dict)

    run.plots = []
    run.figures = []
    with container:
        with ui.column().classes('w-full h-full'):
            for row in range(num_rows):
                with ui.row().classes('w-full justify-start flex-wrap'):
                    for col in range(num_columns):
                        if plot_idx >= num_plots:
                            break
                        fig = create_2d_plot(plot_dict,plot_idx)
                        run.figures.append(fig)
                        width_percent = 100 / num_columns - 2
                        height_percent = 100 / num_rows - 2
                        with ui.column().style(
                            f"width: {width_percent}%; box-sizing: border-box;"
                            f"height: {height_percent}%; box-sizing: border-box;"
                            ):
                            plot = ui.plotly(fig).classes('w-full h-full')\
                                .style(f'min-height: {int(800/num_rows)}px;')
                            run.plots.append(plot)
                        plot_idx += 1
    app.storage.tab["plot_dict_2D"] = plot_dict

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
