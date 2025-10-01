import time
import math

from nicegui import ui
from qcodes.dataset import load_by_id
import xarray as xr

from arbok_inspector.analysis.prepare_data import prepare_and_avg_data
from arbok_inspector.analysis.analysis_base import AnalysisBase
from arbok_inspector.widgets.build_xarray_grid import build_xarray_grid
from arbok_inspector.helpers.unit_formater import unit_formatter

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
        """
        Class representing a dimension of the data
        
        Args:
            name (str): Name of the dimension
            
        Attributes:
            name (str): Name of the dimension
            option (str): Option for the dimension (average, select_value, x-axis, y
            select_index (int): Index of the selected value for select_value option
            ui_element: Reference to the UI element for the dimension
        """
        self.name = name
        self.option = None
        self.select_index = 0
        self.ui_selecter = None

    def __str__(self):
        return self.name

class Run:
    """
    Class representing a run with its data and methods
    """
    def __init__(self, run_id: int):
        """Constructor for Run class"""
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
        """
        Set the default dimension options for the run in 4 steps:
        1. Set all iteration dims to 'average'
        2. Set the innermost dim to 'x-axis' (the last one that is not averaged)
        3. Set the next innermost dim to 'y-axis'
        4. Set all remaining dims to 'select_value'

        Returns:
            options (dict): Dictionary with keys 'average', 'select_value', 'y-axis',
        """
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

    def update_subset_dims(self, dim: Dim, selection: str, index = None):
        text = f'Updating subset dims: {dim.name} to {selection}'
        print(text)
        ui.notify(text, position='top-right')

        ### First, remove old option this dim was on
        if dim.option in ['average', 'select_value']:
            self.dim_axis_option[dim.option].remove(dim)
        if dim.option in ['x-axis', 'y-axis']:
            self.dim_axis_option[dim.option] = None

        ### Now, set new option
        if selection in ['average', 'select_value']:
            # dim.ui_selecter.value = selection
            dim.select_index = index
            self.dim_axis_option[selection].append(dim)

        if selection in ['x-axis', 'y-axis']:
            old_dim = self.dim_axis_option[selection]
            self.dim_axis_option[selection] = dim
            if old_dim is not None:
                print(f"Updating {old_dim.name} to {dim.name} on {selection}")
                if old_dim.option in ['x-axis', 'y-axis']:
                    self.dim_axis_option['select_value'].append(old_dim)
                    old_dim.option = 'select_value'
                    old_dim.ui_selecter.value = 'select_value'
                    # old_dim.ui_selecter.update()
                    self.update_subset_dims(old_dim, 'select_value', old_dim.select_index)
        dim.ui_selecter.update()

    def generate_subset(self):
        # TODO: take the averaging out of this! We only want to average if necessary
        # averaging can be computationally intensive!
        sub_set = self.full_data_set
        for avg_axis in self.dim_axis_option['average']:
            sub_set = sub_set.mean(dim=avg_axis.name)
        sel_dict = {d.name: d.select_index for d in self.dim_axis_option['select_value']}
        sub_set = sub_set.isel(**sel_dict).squeeze()
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
            # with ui.column().classes('light bg-gray-900 text-white p-4 rounded'):
            display_xarray_html(run)

        with ui.expansion('Coordinates and results', icon='expand_more', value=True).classes(
            f'w-full {expansion_borders} gap-4 no-wrap items-start'):
            with ui.row().classes('w-full gap-6 no-wrap items-start'):
                with ui.column().classes('w-1/2 gap-2'):
                    ui.label("Coordinates:").classes('text-lg font-semibold')
                    for dim in run.dims:
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
                    on_click=lambda: print_debug(run),
                    color = 'red'
                ).classes('mr-auto')
            plot_container_ref['value'] = ui.row().classes('w-full p-4')
            build_xarray_grid(run, plot_container_ref['value'])

def add_dim_dropdown(dim: Dim, run: Run):
    placeholder = {"value": None}
    with ui.row().classes('w-full gap-2 no-wrap items-center'):
        ui_element = ui.select(
            options = axis_options,
            value = str(dim.option),
            label = f'{dim.name.replace("__", ".")}',
            on_change = lambda e: update_dim_selection(run, dim, e.value, placeholder["value"])
        ).classes('w-full')
        dim.ui_selecter = ui_element
    placeholder["value"] = ui.column().classes('w-full')

def update_dim_selection(run: Run, dim: Dim, value, placeholder):
    placeholder.clear()
    print(value)
    if value == 'average':
        run.update_subset_dims(dim, 'average')
        dim.option = 'average'
    if value == 'select_value':
        dim_size = run.full_data_set.sizes[dim.name]
        with placeholder:
            slider = ui.slider(
                min=0, max=dim_size - 1, step=1, value=0,
                on_change=lambda e: run.update_subset_dims(dim, 'select_value', e.value)
            ).classes('w-full h-4')
            label = ui.label('').classes('ml-4')
            update_value_from_dim_slider(label, slider, run, dim)
            slider.on(
                'update:model-value',
                lambda e: update_value_from_dim_slider(label, slider, run, dim),
                throttle=0.2, leading_events=False)
        run.update_subset_dims(dim, 'select_value', 0)
    else:
        run.update_subset_dims(dim, value)
        dim.option = value
    build_xarray_grid(run, plot_container_ref['value'])

def update_value_from_dim_slider(label, slider, run: Run, dim: Dim):
    """Update the label next to the slider with the current value and unit."""
    label_txt = f'Value: {unit_formatter(run, dim, slider.value)}'
    label.text = label_txt
    build_xarray_grid(run, plot_container_ref['value'])

def set_plots_per_column(value: int, run: Run):
    ui.notify(f'Setting plots per column to {value}', position='top-right')
    run.plots_per_column = int(value)
    build_xarray_grid(run, plot_container_ref['value'])

def print_debug(run: Run):
    print("Debugging Run:")
    for key, val in run.dim_axis_option.items():
        if isinstance(val, list):
            val_str = str([d.name for d in val])
        elif isinstance(val, Dim):
            val_str = val.name
        else:
            val_str = str(val)
        print(f"{key}: \t {val_str}")


def display_xarray_html(run):
    """Display the xarray dataset in a dark-themed style."""
    ds = run.full_data_set
    with ui.column().classes('w-full'):
        ui.html('''
        <style>
        /* Wrap styles to only apply inside this container */
        .xarray-dark-wrapper {
            background-color: #343535; /* Tailwind gray-800 */
            color: #ffffff;
            padding: 1rem;
            border-radius: 0.5rem;
            overflow-x: auto;
        }

        .xarray-dark-wrapper th,
        .xarray-dark-wrapper td {
            color: #d1d5db; /* Tailwind gray-300 */
            background-color: transparent;
        }

        .xarray-dark-wrapper .xr-var-name {
            color: #93c5fd !important; /* Tailwind blue-300 */
        }

        .xarray-dark-wrapper .xr-var-dims,
        .xarray-dark-wrapper .xr-var-data {
            color: #d1d5db !important; /* Light gray */
        }

        /* Optional: override any inline black text */
        .xarray-dark-wrapper * {
            color: inherit !important;
            background-color: transparent !important;
        }
        </style>
        ''')

        # Wrap the dataset HTML in a div with that class
        ui.html(f'''
        <div class="xarray-dark-wrapper">
        {ds._repr_html_()}
        </div>
        ''')