"""Module to build a grid of xarray plots for a given run."""
import math
import plotly.graph_objects as go
from nicegui import ui

def build_xarray_grid(run, container):
    container.clear()
    print('plotting!')
    ds = run.generate_subset()
    keys = run.plot_selection
    num_plots = len(keys)
    num_columns = int(min([run.plots_per_column, len(keys)]))
    num_rows = math.ceil(num_plots / num_columns)
    pretty_keys = [key.replace("__", ".") for key in keys]

    x_dim = run.dim_axis_option['x-axis'].name
    y_dim = run.dim_axis_option['y-axis'].name
    plot_idx = 0
    def create_plot(row, col, plot_idx):
        key = keys[plot_idx]
        da = ds[key]
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
        fig.update_layout(
            template = 'plotly_dark',
            autosize=True,
            margin=dict(l=40, r=40, t=40, b=40),
            xaxis_title=x_dim.replace("__", ".") + f" ({da.coords[x_dim].unit})",
            yaxis_title=y_dim.replace("__", ".") + f" ({da.coords[y_dim].unit})",
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
                        fig = create_plot(row, col, plot_idx)
                        width_percent = 100 / num_columns - 2
                        with ui.column().style(
                            f"width: {width_percent}%; box-sizing: border-box;"
                            ):
                            ui.plotly(fig).classes('w-full').style('min-height: 300px;')
                        plot_idx += 1
