"""Module to build a grid of xarray plots for a given run."""
import math
import copy
import plotly.graph_objects as go
from nicegui import ui

from arbok_inspector.helpers.unit_formater import unit_formatter

def build_xarray_grid(run, container):
    container.clear()
    ds = run.generate_subset()
    print(f"Found {len(ds.dims)} dimensions to plot in subset:")
    if len(ds.dims) == 1:
        create_1d_plot(run, ds, container)
    elif len(ds.dims) == 2:
        create_2d_grid(run, ds, container)

def create_1d_plot(run, ds, container):
    fig = go.Figure()
    x_dim = run.dim_axis_option['x-axis'].name
    for key in run.plot_selection:
        da = ds[key]
        fig.add_trace(
            go.Scatter(
                x=da.coords[x_dim].values,
                y=da.values,
                mode='lines+markers',
                name=key.replace("__", "."),
            )
        )
    title = ''
    for dim in run.dim_axis_option['select_value']:
        title += f"{dim.name } = {unit_formatter(run, dim, dim.select_index)}<br>"
    x_dim_list = x_dim.split('__')
    fig.update_layout(
        template = 'plotly_dark',
        autosize=True,
        margin=dict(l=40, r=40, t=40, b=40),
        xaxis_title=f"{'.'.join(x_dim_list[:-1])}.<b>{x_dim_list[-1]}</b>  ({da.coords[x_dim].unit})",
        title=dict(
            text=title,
            x=0.5,
            xanchor='center',
            yanchor = 'bottom',
            font = dict(size=16)
            ),
        legend=dict(
            x=1,
            y=1,
            xanchor='right',
            yanchor='top',
            bgcolor='rgba(0,0,0,0.5)',
            bordercolor='white',
            borderwidth=1,
        )
    )
    with container:
        ui.plotly(fig).classes('w-full').style('min-height: 400px;')

def create_2d_grid(run, ds, container):
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
    plot_idx = 0
    def create_2d_plot(row, col, plot_idx):
        key = keys[plot_idx]
        da = ds[key]
        if x_dim != da.dims[1]:
            da = da.transpose(y_dim, x_dim)
        fig = go.Figure(
            data=go.Heatmap(
                z=da.values,
                x=da.coords[x_dim].values,
                y=da.coords[y_dim].values,
                colorscale='magma',
                colorbar=dict(
                    thickness=10,
                    xanchor='left',
                    x= 1.0,
                ),
                showscale=True,
            )
        )
        x_dim_list = x_dim.split('__')
        y_dim_list = y_dim.split('__')
        fig.update_layout(
            template = 'plotly_dark',
            autosize=True,
            margin=dict(l=40, r=40, t=40, b=40),
            xaxis_title=f"{'.'.join(x_dim_list[:-1])}.<b>{x_dim_list[-1]}</b>  ({da.coords[x_dim].unit})",
            yaxis_title=f"{'.'.join(y_dim_list[:-1])}.<b>{y_dim_list[-1]}</b>  ({da.coords[y_dim].unit})",
            title=dict(
                text=pretty_keys[plot_idx],
                x=0.5,
                xanchor='center',
                yanchor = 'bottom',
                font = dict(size=16)
                ),
        )
        return fig

    with container:
        with ui.column().classes('w-full'):
            for row in range(num_rows):
                with ui.row().classes('w-full justify-start flex-wrap'):
                    for col in range(num_columns):
                        if plot_idx >= num_plots:
                            break
                        fig = create_2d_plot(row, col, plot_idx)
                        width_percent = 100 / num_columns - 2
                        with ui.column().style(
                            f"width: {width_percent}%; box-sizing: border-box;"
                            ):
                            ui.plotly(fig).classes('w-full').style('min-height: 300px;')
                        plot_idx += 1
