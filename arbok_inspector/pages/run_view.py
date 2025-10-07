"""Run view page showing the data and plots for a specific run"""
from __future__ import annotations
from typing import TYPE_CHECKING
import json
import importlib.resources as resources

from nicegui import ui, app

from arbok_inspector.widgets.build_xarray_grid import build_xarray_grid
from arbok_inspector.widgets.build_xarray_html import build_xarray_html
from arbok_inspector.widgets.json_plot_settings_dialog import JsonPlotSettingsDialog
from arbok_inspector.helpers.unit_formater import unit_formatter
from arbok_inspector.classes.run import Run


from arbok_inspector.classes.dim import Dim

RUN_TABLE_COLUMNS = [
    {'field': 'name', 'filter': 'agTextColumnFilter', 'floatingFilter': True},
    {'field': 'size'},
    {'field': 'x', 'checkboxSelection': True},
    {'field': 'y', 'checkboxSelection': True},
    {'field': 'average', 'checkboxSelection': True},
]

AXIS_OPTIONS = ['average', 'select_value', 'y-axis', 'x-axis']


EXPANSION_CLASSES = 'w-full p-0 gap-1 border border-gray-400 rounded-lg no-wrap items-start'

@ui.page('/run/{run_id}')
async def run_page(run_id: str):
    """
    Page showing the details and plots for a specific run.

    Args:
        run_id (str): ID of the run to display
    """
    ui.page_title(f"{run_id}")
    _ = await ui.context.client.connected()
    run = Run(int(run_id))
    app.storage.tab["placeholders"] = {'plots': None}
    app.storage.tab["run"] = run
    with resources.files("arbok_inspector.configurations").joinpath("1d_plot.json").open("r") as f:
        app.storage.tab["plot_dict_1D"] = json.load(f)
    with resources.files("arbok_inspector.configurations").joinpath("2d_plot.json").open("r") as f:
        app.storage.tab["plot_dict_2D"] = json.load(f)

    ui.label(f'Run Page for ID: {run_id}').classes('text-2xl font-bold mb-6')
    with ui.column().classes('w-full gap-1'):
        with ui.expansion('Coordinates and results', icon='checklist', value=True)\
            .classes(EXPANSION_CLASSES).props('expand-separator'):
            with ui.row().classes('w-full gap-4 no-wrap items-start'):
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
        with ui.expansion('Plots', icon='stacked_line_chart', value=True)\
            .classes(EXPANSION_CLASSES):
            with ui.row().classes('w-full p-2 gap-2 items-center rounded-md border border-neutral-600 bg-neutral-800 text-sm'):
                
                ui.button(
                    text='Update',
                    icon='refresh',
                    color='green',
                    on_click=lambda: build_xarray_grid(),
                ).classes('h-8 px-2')

                ui.button(
                    text='Debug',
                    icon='info',
                    color='red',
                    on_click=lambda: print_debug(run),
                ).classes('h-8 px-2')

                dialog_1d = JsonPlotSettingsDialog('plot_dict_1D')
                dialog_2d = JsonPlotSettingsDialog('plot_dict_2D')

                ui.button(
                    text='1D settings',
                    color='pink',
                    on_click=dialog_1d.open,
                ).classes('h-8 px-2')

                ui.button(
                    text='2D settings',
                    color='orange',
                    on_click=dialog_2d.open,
                ).classes('h-8 px-2')

                ui.number(
                    label='# per col',
                    value=2,
                    format='%.0f',
                    on_change=lambda e: set_plots_per_column(e.value),
                ).props('dense outlined').classes('w-20 h-8 text-xs mb-2')
                #.style('line-height: 1rem; padding-top: 0; padding-bottom: 0;')
            app.storage.tab["placeholders"]["plots"] = ui.row().classes('w-full p-4')
            build_xarray_grid()
        with ui.expansion('xarray summary', icon='summarize', value=False)\
            .classes(EXPANSION_CLASSES):
            build_xarray_html()
        with ui.expansion('analysis', icon='science', value=False)\
            .classes(EXPANSION_CLASSES):
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
    with ui.row().classes('w-full no-wrap items-center gap-1'):
        ui_element = ui.select(
            options = AXIS_OPTIONS,
            value = str(dim.option),
            label = f'{dim.name.replace("__", ".")}',
            on_change = lambda e: update_dim_selection(
                dim, e.value, local_placeholder["slider"])
        ).classes(f"{width} text-sm m-0 p-0").props('dense')
        dim.ui_selector = ui_element
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
            with ui.row().classes("w-full items-center"):
                with ui.column().classes('flex-grow'):
                    slider = ui.slider(
                        min=0, max=dim_size - 1, step=1, value=0,
                        on_change=lambda e: run.update_subset_dims(dim, 'select_value', e.value),
                        ).classes('flex-grow')\
                        .props('color="purple" markers label-always')
                label = ui.html('').classes('shrink-0 text-right px-2 py-1 bg-purple text-white rounded-lg text-xs font-normal text-center')
                update_value_from_dim_slider(label, slider, dim)
                slider.on(
                    'update:model-value',
                    lambda e: update_value_from_dim_slider(label, slider, dim),
                    throttle=0.2, leading_events=False)
        run.update_subset_dims(dim, 'select_value', 0)
    else:
        run.update_subset_dims(dim, value)
        dim.option = value
    build_xarray_grid()

def update_value_from_dim_slider(label, slider, dim: Dim):
    """
    Update the label next to the slider with the current value and unit.
    
    Args:
        label: The UI label to update
        slider: The UI slider to get the value from
        dim (Dim): The dimension object
    """
    run = app.storage.tab["run"]
    label_txt = f' {unit_formatter(run, dim, slider.value)} '
    label.set_content(label_txt)
    build_xarray_grid()

def set_plots_per_column(value: int):
    """
    Set the number of plots to display per column.

    Args:
        value (int): The number of plots per column
    """
    run = app.storage.tab["run"]
    ui.notify(f'Setting plots per column to {value}', position='top-right')
    run.plots_per_column = int(value)
    build_xarray_grid()


def update_sweep_dim_name(dim: Dim, new_name: str):
    """
    Update the name of the dimension in the sweep dict and the dim object.
    
    Args:
        dim (Dim): The dimension object to update
        new_name (str): The new name for the dimension
    """
    run = app.storage.tab["run"]
    dim.name = new_name
    dim.ui_selector.label = new_name.replace("__", ".")
    build_xarray_grid()

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