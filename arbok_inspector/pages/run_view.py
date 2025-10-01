import time
import math

from nicegui import ui
from qcodes.dataset import load_by_id
import xarray as xr

from arbok_inspector.analysis.prepare_data import prepare_and_avg_data
from arbok_inspector.analysis.analysis_base import AnalysisBase
from arbok_inspector.widgets.build_xarray_grid import build_xarray_grid

run_table_columns = [
    {'field': 'name', 'filter': 'agTextColumnFilter', 'floatingFilter': True},
    {'field': 'size'},
    {'field': 'x', 'checkboxSelection': True},
    {'field': 'y', 'checkboxSelection': True},
    {'field': 'average', 'checkboxSelection': True},
]

axis_options = ['average', 'select_value', 'y-axis', 'x-axis']
plot_container_ref = {'value': None}

class Dim:
    def __init__(self, name):
        self.name = name
        self.option = None
        self.select_index = 0
        self.ui_element = None

    def __str__(self):
        return self.name

class Run:
    def __init__(self, run_id: int):
        self.run_id = run_id
        self.title = f'Run ID: {run_id}  (-> add experiment)'
        self.full_data_set = load_by_id(run_id).to_xarray_dataset()
        self.full_sub_set = None
        self.dims = [Dim(name) for name in self.full_data_set.dims]
        self.dim_axis_option = self.set_dim_axis_option()

        self.subset_dims = {name: None for name in self.full_data_set.dims}
        self.plot_selection = []
        self.plots_per_column = 2

    def set_dim_axis_option(self):
        options = {x: [] for x in axis_options} 
        for dim in self.dims:
            if 'iteration' in dim.name:
                dim.option = 'average'
                options['average'].append(dim)
        for dim in reversed(self.dims):
            if dim not in options['average'] and dim != options['x-axis']:
                dim.option = "x-axis"
                options['x-axis'] = dim
                print(f"Setting x-axis to {dim.name}")
                break
        for dim in reversed(self.dims):
            if dim not in options['average'] and dim != options['x-axis']:
                dim.option = 'y-axis'
                options['y-axis'] = dim
                print(f"Setting y-axis to {dim.name}")
                break
        for dim in self.dims:
            if dim not in options['average'] and dim != options['x-axis'] and dim != options['y-axis']:
                dim.option = 'select_value'
                options['select_value'].append(dim)
                dim.select_index = 0
                print(f"Setting select_value to {dim.name}")
        return options

    def display_summary(self):
        ui.html(self.full_data_set._repr_html_())

    def update_subset_dims(self, dim: Dim, action: str, selection = None):
        ui.notify(f'Updated subset with {action} on {dim.name}', position='top-right')
        dim.ui_element.value = action

    def generate_subset(self):
        # TODO: take the averaging out of this! We only want to average if necessary
        # averaging can be computationally intensive!
        sub_set = self.full_data_set
        for avg_axis in self.dim_axis_option['average']:
            sub_set = sub_set.mean(dim=avg_axis.name)

        for dim in self.dim_axis_option['select_value']:
            indx = dim.select_index
            sub_set = sub_set.isel({dim.name: indx})
        return sub_set

    def update_plot_selection(self, value: bool, readout_name: str):
        print(f"{readout_name= } {value= }")
        pretty_readout_name = readout_name.replace("__", ".")
        if readout_name not in self.plot_selection:
            self.plot_selection.append(readout_name)
            ui.notify(f'Result {pretty_readout_name} added to plot selection', position='top-right')
        else:
            self.plot_selection.remove(readout_name)
            ui.notify(f'Result {pretty_readout_name} removed from plot selection', position='top-right')
        print(f"{self.plot_selection= }")
        build_xarray_grid(self, plot_container_ref['value'])

expansion_borders = 'border border-gray-400 rounded-lg'

@ui.page('/run/{run_id}')
async def run_page(run_id: str):
    run = Run(int(run_id))

    ui.label(f'Run Page for ID: {run_id}').classes('text-2xl font-bold mb-6')

    with ui.column().classes('w-full'):
        with ui.expansion('xarray summary', icon='expand_more', value=False).classes(
            f'w-full {expansion_borders} gap-4 no-wrap items-start'):
            run.display_summary()

        with ui.expansion('Coordinates and results', icon='expand_more', value=True).classes(
            f'w-full {expansion_borders} gap-4 no-wrap items-start'):
            with ui.row().classes('w-full gap-4 no-wrap items-start'):
                with ui.column().classes('w-1/2 gap-4'):
                    ui.label("Coordinates:").classes('text-lg font-semibold')
                    for dim in run.dims:
                        # fix select_value!!
                        add_dim_dropdown(dim, run)

                with ui.column().classes('w-1/2 gap-4'):
                    ui.label("Results:").classes('text-lg font-semibold')
                    row_data = [{'name': result.replace("__", ".")} for result in run.full_data_set]
                    for i, result in enumerate(run.full_data_set):
                        if i == 0:
                            ## TODO: save checkboxes in dict and read values for plotting!
                            value = True
                            run.plot_selection.append(result) 
                        else:
                            value = False
                        ui.checkbox(
                            text = result.replace("__", "."),
                            value = value,
                            on_change = lambda e, r=result: run.update_plot_selection(e.value, r),
                        ).classes('text-sm h-4')

        with ui.expansion(
            'Plots',
            icon='expand_more', value=True).classes(
                f'w-full {expansion_borders} gap-4 no-wrap items-start'):
            
            with ui.row().classes('w-full p-4'):
                ui.button(
                    text = 'Update plots',
                    icon = 'refresh',
                    color='green',
                    on_click=lambda: build_xarray_grid(
                        run, plot_container_ref['value']),
                ).classes('ml-auto')
                ui.number(
                    label = '# plots per column',
                    value = 2,
                    format = '%.0f',
                    on_change = lambda e: set_plots_per_column(e.value, run)
                ).classes('mx-auto')
                ui.button(
                    text = 'Show dims',
                    icon = 'info',
                    on_click=lambda: print(run.dim_axis_option),
                    color = 'red'
                ).classes('mr-auto')
            plot_container_ref['value'] = ui.row().classes('w-full p-4')
            build_xarray_grid(run, plot_container_ref['value'])

def add_dim_dropdown(dim: Dim, run: Run):
    with ui.row().classes('w-full'):
        with ui.row().classes('w-1/2'):
            select_placeholder = ui.column().classes()
        with ui.row().classes('w-1/3'):
            with ui.row():
                slider_placeholder = ui.column().classes()
            with ui.row().classes('w-1/6'):
                label_placeholder = ui.column().classes()
        placeholders = (slider_placeholder, label_placeholder)
        ui_element = ui.select(
            options = axis_options,
            value = str(dim.option),
            label = f'{dim.name.replace("__", ".")}',
            on_change = lambda e: update_dim_selection(run, dim, e.value, placeholders)
        ).classes('w-1/2 h-4')
        ui_element.parent = select_placeholder
        dim.ui_element = ui_element

def update_dim_selection(run: Run, dim: Dim, value, placeholders):
    slider_placeholder, label_placeholder = placeholders
    slider_placeholder.clear()
    label_placeholder.clear()
    print(value)
    if value == 'average':
        run.update_subset_dims(dim, 'average')
        dim.option = 'average'
    if value == 'select_value':
        dim_size = run.full_data_set.sizes[dim.name]
        slider = ui.slider(
            min=0, max=dim_size - 1, step=1, value=0,
            on_change=lambda e: print(e.value)
        ).classes('w-1/2')
        slider.props('label-always')
        slider.parent = slider_placeholder
        slider.on(
            'update:model-value', lambda e: update_value_from_slider(label, slider, run, dim),
            throttle=0.2, leading_events=False)
        label = ui.label(f'Value: {run.full_data_set[dim.name].values[0]}').classes('ml-4')
        ui.label().bind_text_from(slider, 'value')
    if value == 'x-axis':
        run.update_subset_dims(dim, 'x-axis')
        dim.option = 'x-axis'
    if value == 'y-axis':
        run.update_subset_dims(dim, 'y-axis')
        dim.option = 'y-axis'

def update_value_from_slider(label, slider, run: Run, dim: Dim):
    label.text = f'Value: {run.full_data_set[dim.name].values[slider.value]}'
    run.select_index(dim.name, slider.value)

    lambda e: run.select_index(dim, e.args)

def set_plots_per_column(value: int, run: Run):
    ui.notify(f'Setting plots per column to {value}', position='top-right')
    run.plots_per_column = int(value)
    build_xarray_grid(run, plot_container_ref['value'])
