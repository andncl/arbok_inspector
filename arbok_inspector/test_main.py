import numpy as np
import xarray as xr
import plotly.express as px
from nicegui import ui

# --- Create a sample 4D DataArray ---
data = np.random.rand(5, 10, 20, 30)  # shape: time, depth, y, x
coords = {
    'time': np.arange(5),
    'depth': np.linspace(0, 100, 10),
    'y': np.linspace(-5, 5, 20),
    'x': np.linspace(-5, 5, 30),
}
array = xr.DataArray(data, dims=('time', 'depth', 'y', 'x'), coords=coords)

# --- Define axes to plot ---
x_dim = 'x'
y_dim = 'y'
slider_dims = [dim for dim in array.dims if dim not in (x_dim, y_dim)]

# --- UI State ---
slider_values = {dim: 0 for dim in slider_dims}
plot_container = ui.row().classes('w-full justify-center')

# --- Heatmap update function ---
def update_plot():
    # Index the array using current slider values
    sel = {dim: slider_values[dim] for dim in slider_dims}
    slice_2d = array.isel(**sel)

    # Convert to plotly figure
    fig = px.imshow(
        slice_2d.values,
        labels={'x': x_dim, 'y': y_dim},
        x=array.coords[x_dim].values,
        y=array.coords[y_dim].values,
        color_continuous_scale='Viridis',
    )
    fig.update_layout(title=f'{x_dim} vs {y_dim} | ' + ', '.join([f'{dim}={slider_values[dim]}' for dim in slider_dims]))

    plot_container.clear()
    with plot_container:
        ui.plotly(fig).classes('max-w-3xl max-h-96')

# --- Create sliders for all non-plotted dimensions ---
for dim in slider_dims:
    max_index = len(array.coords[dim]) - 1
    def make_slider(d=dim):
        def on_change(val):
            slider_values[d] = int(val)
            update_plot()
        ui.slider(
            min=0,
            max=max_index,
            value=0,
            step=1,
            on_change=on_change,
            #abel=f'{d} ({array.coords[d].values[0]})'
        ).props('label-always').classes('w-full')
    make_slider()

# --- Initial plot ---
update_plot()

ui.run()
