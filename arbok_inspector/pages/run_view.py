"""Run view page showing the data and plots for a specific run"""
import json

from nicegui import ui, app
from qcodes.dataset import load_by_id

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
placeholders = {'plots': None}

class Dim:
    """
    Class representing a dimension of the data
    """
    def __init__(self, name):
        """
       Constructor for Dim class
        
        Args:
            name (str): Name of the dimension
            
        Attributes:
            name (str): Name of the dimension
            option (str): Option for the dimension (average, select_value, x-axis, y-axis)
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
        """
        Constructor for Run class
        
        Args:
            run_id (int): ID of the run
        """
        self.run_id = run_id
        self.title = f'Run ID: {run_id}  (-> add experiment)'
        self.dataset = load_by_id(run_id)
        self.full_data_set = self.dataset.to_xarray_dataset()
        self.full_sub_set = None
        
        self.together_sweeps = False
        
        self.parallel_sweep_axes = {}
        self.sweep_dict = {}
        self.load_sweep_dict()
        self.dims = list(self.sweep_dict.values())
        print(self.dims)
        self.dim_axis_option = self.set_dim_axis_option()

        self.subset_dims = {name: None for name in self.full_data_set.dims}
        self.plot_selection = []
        self.plots_per_column = 2

    def load_sweep_dict(self):
        """
        Load the sweep dictionary from the dataset
        TODO: check metadata for sweep information!
        Returns:
            sweep_dict (dict): Dictionary with sweep information
            is_together (bool): True if all sweeps are together, False otherwise
        """
        if "parallel_sweep_axes" in self.dataset.metadata:
            conf = self.dataset.metadata["parallel_sweep_axes"]
            conf = conf.replace("'", '"')  # Ensure JSON compatibility
            print( conf)
            conf = json.loads(conf)
            self.parallel_sweep_axes = {int(i): sweeps for i, sweeps in conf.items()}
            self.together_sweeps = True
        else:
            dims = self.full_data_set.dims
            self.parallel_sweep_axes = {i: [dim] for i, dim in enumerate(dims)}
            self.together_sweeps = False
        self.sweep_dict = {
            i: Dim(names[0]) for i, names in self.parallel_sweep_axes.items()
            }
        print(self.sweep_dict)
        return self.sweep_dict

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
        """
        Update the subset dimensions based on user selection.

        Args:
            dim (Dim): The dimension object to update
            selection (str): The new selection option
                ('average', 'select_value', 'x-axis', 'y-axis')
            index (int, optional): The index for 'select_value' option. Defaults to None.
        """
        text = f'Updating subset dims: {dim.name} to {selection}'
        print(text)
        ui.notify(text, position='top-right')

        ### First, remove old option this dim was on
        for option in ['average', 'select_value']:
            if dim in self.dim_axis_option[option]:
                self.dim_axis_option[option].remove(dim)
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
                # Set previous dim (having this option) to 'select_value'
                # Required since x and y axis ahve to be unique
                print(f"Updating {old_dim.name} to {dim.name} on {selection}")
                if old_dim.option in ['x-axis', 'y-axis']:
                    self.dim_axis_option['select_value'].append(old_dim)
                    old_dim.option = 'select_value'
                    old_dim.ui_selecter.value = 'select_value'
                    self.update_subset_dims(old_dim, 'select_value', old_dim.select_index)
        dim.ui_selecter.update()

    def generate_subset(self):
        """
        Generate the subset of the full dataset based on the current dimension options.
        Returns:
            sub_set (xarray.Dataset): The subset of the full dataset
        """
        # TODO: take the averaging out of this! We only want to average if necessary
        # averaging can be computationally intensive!
        sub_set = self.full_data_set
        for avg_axis in self.dim_axis_option['average']:
            sub_set = sub_set.mean(dim=avg_axis.name)
        sel_dict = {d.name: d.select_index for d in self.dim_axis_option['select_value']}
        sub_set = sub_set.isel(**sel_dict).squeeze()
        return sub_set

    def update_plot_selection(self, value: bool, readout_name: str):
        """
        Update the plot selection based on user interaction.

        Args:
            value (bool): True if the result is selected, False otherwise
            readout_name (str): Name of the result to update
        """
        print(f"{readout_name= } {value= }")
        pretty_readout_name = readout_name.replace("__", ".")
        if readout_name not in self.plot_selection:
            self.plot_selection.append(readout_name)
            ui.notify(
                message=f'Result {pretty_readout_name} added to plot selection',
                position='top-right'
                )
        else:
            self.plot_selection.remove(readout_name)
            ui.notify(
                f'Result {pretty_readout_name} removed from plot selection',
                position='top-right'
            )
        print(f"{self.plot_selection= }")
        build_xarray_grid(self)

expansion_borders = 'border border-gray-400 rounded-lg'

@ui.page('/run/{run_id}')
async def run_page(run_id: str):
    """
    Page showing the details and plots for a specific run.

    Args:
        run_id (str): ID of the run to display
    """
    client = await ui.context.client.connected()
    run = Run(int(run_id))
    app.storage.tab["placeholders"] = placeholders
    app.storage.tab["run"] = run

    ui.label(f'Run Page for ID: {run_id}').classes('text-2xl font-bold mb-6')
    with ui.column().classes('w-full'):
        with ui.expansion('Coordinates and results', icon='checklist', value=True).classes(
            f'w-full {expansion_borders} gap-4 no-wrap items-start'):
            with ui.row().classes('w-full gap-6 no-wrap items-start'):
                with ui.column().classes('w-2/3 gap-2'):
                    ui.label("Coordinates:").classes('text-lg font-semibold')
                    for i, _ in run.parallel_sweep_axes.items():
                        add_dim_dropdown(sweep_idx = i)
                with ui.column().classes('w-1/3 gap-2'):
                    ui.label("Results:").classes('text-lg font-semibold')
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
                        ).classes('text-sm h-4').props('color=purple')
        with ui.expansion(
            'Plots',
            icon='stacked_line_chart', value=True).classes(
                f'w-full {expansion_borders} gap-4 no-wrap items-start'):
            with ui.row().classes('w-full p-4'):
                ui.button(
                    text = 'Update plots',
                    icon = 'refresh',
                    color='green',
                    on_click=lambda: build_xarray_grid(run),
                ).classes('ml-auto')
                ui.number(
                    label = '# plots per column',
                    value = 2,
                    format = '%.0f',
                    on_change = lambda e: set_plots_per_column(e.value)
                ).classes('mx-auto')
                ui.button(
                    text = 'Show dims',
                    icon = 'info',
                    on_click=lambda: print_debug(run),
                    color = 'red'
                ).classes('mr-auto')
            app.storage.tab["placeholders"]["plots"] = ui.row().classes('w-full p-4')
            build_xarray_grid(run)
        with ui.expansion('xarray summary', icon='summarize', value=False).classes(
            f'w-full {expansion_borders} gap-4 no-wrap items-start'):
            display_xarray_html()
        with ui.expansion('analysis', icon='science', value=False).classes(
            f'w-full {expansion_borders} gap-4 no-wrap items-start'):
            with ui.row():
                ui.label("Working on it!  -Andi").classes('text-lg font-semibold')

def add_dim_dropdown(sweep_idx: int):
    """
    Add a dropdown to select the dimension option for a given sweep index.

    Args:
        sweep_idx (int): Index of the sweep to add the dropdown for
    """
    run = app.storage.tab["run"]
    width = 'w-1/2' if run.together_sweeps else 'w-full'
    dim = run.sweep_dict[sweep_idx]
    local_placeholder = {"slider": None}
    with ui.row().classes('w-full gap-2 no-wrap items-center'):
        ui_element = ui.select(
            options = axis_options,
            value = str(dim.option),
            label = f'{dim.name.replace("__", ".")}',
            on_change = lambda e: update_dim_selection(dim, e.value, local_placeholder["slider"])
        ).classes(width)
        dim.ui_selecter = ui_element
        if run.together_sweeps:
            dims_names = run.parallel_sweep_axes[sweep_idx]
            ui.radio(
                options = dims_names,
                value=dim.name,
                on_change = lambda e: update_sweep_dim_name(dim, e.value)
                ).classes(width).props('dense')
    local_placeholder["slider"] = ui.column().classes('w-full')

def update_dim_selection(dim: Dim, value: str, slider_placeholder):
    """
    Update the dimension/sweep selection and rebuild the plot grid.

    Args:
        dim (Dim): The dimension object to update
        value (str): The new selection value
        slider_placeholder: The UI placeholder to update
    """
    run = app.storage.tab["run"]
    slider_placeholder.clear()
    print(value)
    if value == 'average':
        run.update_subset_dims(dim, 'average')
        dim.option = 'average'
    if value == 'select_value':
        dim_size = run.full_data_set.sizes[dim.name]
        with slider_placeholder:
            slider = ui.slider(
                min=0, max=dim_size - 1, step=1, value=0,
                on_change=lambda e: run.update_subset_dims(dim, 'select_value', e.value),
                ).classes('w-full h-4')\
                .props('color="purple" markers label-always')
            label = ui.label('').classes('ml-4')
            update_value_from_dim_slider(label, slider, dim)
            slider.on(
                'update:model-value',
                lambda e: update_value_from_dim_slider(label, slider, dim),
                throttle=0.2, leading_events=False)
        run.update_subset_dims(dim, 'select_value', 0)
    else:
        run.update_subset_dims(dim, value)
        dim.option = value
    build_xarray_grid(run)

def update_value_from_dim_slider(label, slider, dim: Dim):
    """
    Update the label next to the slider with the current value and unit.
    
    Args:
        label: The UI label to update
        slider: The UI slider to get the value from
        dim (Dim): The dimension object
    """
    run = app.storage.tab["run"]
    # label_txt = f'Value: {unit_formatter(run, dim, slider.value)}'
    # label.text = label_txt
    build_xarray_grid(run)

def set_plots_per_column(value: int):
    """
    Set the number of plots to display per column.

    Args:
        value (int): The number of plots per column
    """
    run = app.storage.tab["run"]
    ui.notify(f'Setting plots per column to {value}', position='top-right')
    run.plots_per_column = int(value)
    build_xarray_grid(run)


def update_sweep_dim_name(dim: Dim, new_name: str):
    """
    Update the name of the dimension in the sweep dict and the dim object.
    
    Args:
        dim (Dim): The dimension object to update
        new_name (str): The new name for the dimension
    """
    run = app.storage.tab["run"]
    dim.name = new_name
    dim.ui_selecter.label = new_name.replace("__", ".")
    build_xarray_grid(run)

def display_xarray_html():
    """Display the xarray dataset in a dark-themed style."""
    run = app.storage.tab["run"]
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

def print_debug(run: Run):
    print("\nDebugging Run:")
    for key, val in run.dim_axis_option.items():
        if isinstance(val, list):
            val_str = str([d.name for d in val])
        elif isinstance(val, Dim):
            val_str = val.name
        else:
            val_str = str(val)
        print(f"{key}: \t {val_str}")