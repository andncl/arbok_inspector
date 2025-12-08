"""Run view page showing the data and plots for a specific run"""
from __future__ import annotations
from typing import TYPE_CHECKING
import json
import importlib.resources as resources

from nicegui import ui, app
from nicegui import run as nicegui_run

from arbok_inspector.state import inspector
from arbok_inspector.widgets.build_xarray_grid import build_xarray_grid
from arbok_inspector.widgets.build_xarray_html import build_xarray_html
from arbok_inspector.widgets.build_run_view_actions import build_run_view_actions
from arbok_inspector.helpers.unit_formater import unit_formatter
from arbok_inspector.classes.qcodes_run import QcodesRun
from arbok_inspector.classes.native_run import NativeRun

from arbok_inspector.classes.dim import Dim

if TYPE_CHECKING:
    from nicegui.elements.slider import Slider
    from arbok_inspector.classes.base_run import BaseRun

RUN_TABLE_COLUMNS = [
    {'field': 'name', 'filter': 'agTextColumnFilter', 'floatingFilter': True},
    {'field': 'size'},
    {'field': 'x', 'checkboxSelection': True},
    {'field': 'y', 'checkboxSelection': True},
    {'field': 'average', 'checkboxSelection': True},
]

AXIS_OPTIONS = ['average', 'select_value', 'y-axis', 'x-axis']

EXPANSION_CLASSES = 'w-full p-0 gap-1 border border-gray-400 rounded-lg no-wrap items-start pt-0 mt-0'
TITLE_CLASSES = 'text-lg font-semibold'

@ui.page('/run/{run_id}')
async def run_page(run_id: str):
    """
    Page showing the details and plots for a specific run.

    Args:
        run_id (str): ID of the run to display
    """
    ui.page_title(f"{run_id}")
    run_id = int(run_id)
    _ = await ui.context.client.connected()
    app.storage.tab["qcodes_db_path"] = inspector.qcodes_database_path
    if 'run' in app.storage.tab:
        print('run already exists!')
    with ui.dialog() as loading_dialog:
        with ui.card().classes('p-6 items-center'):
            ui.label('Loading dataset...')
            ui.spinner(size='lg')
    loading_dialog.open()
    try:
        run = await create_run(run_id)
        app.storage.tab["run"] = run
    except Exception as e:
        loading_dialog.close()
        ui.notify(f"Error loading run: {e}", type="error", close_button="OK")
        print("Error in create_run:", e)
        ui.label("Failed to load run!")
        return
    finally:
        if loading_dialog.visible:
            loading_dialog.close()
    app.storage.tab["placeholders"] = {'plots': None}
    app.storage.tab["run"] = run
    with resources.files("arbok_inspector.configurations").joinpath("1d_plot.json").open("r") as f:
        app.storage.tab["plot_dict_1D"] = json.load(f)
    with resources.files("arbok_inspector.configurations").joinpath("2d_plot.json").open("r") as f:
        app.storage.tab["plot_dict_2D"] = json.load(f)

    with ui.row().classes('w-full gap-4'):
        with ui.column().classes('flex-none'):
            with ui.card().classes('w-full gap-0 p-2'):
                ui.label(f'Run-ID: {run_id}').classes('text-2xl font-bold')
            with ui.card().classes('w-full gap-2'):
                ui.label("Coordinates:").classes('text-lg font-semibold pl-2')
                ui.separator().classes('w-full my-1')
                for i, _ in run.parallel_sweep_axes.items():
                    add_dim_dropdown(sweep_idx = i)
            with ui.card().classes('w-full gap-2'):
                ui.label("Results:").classes(TITLE_CLASSES)
                for i, result in enumerate(run.full_data_set):
                    value = False
                    if result in run.plot_selection:
                        value = True
                    ui.checkbox(
                        text = result.replace("__", "."),
                        value = value,
                        on_change = lambda e, r=result: run.update_plot_selection(e.value, r),
                    ).classes('text-sm h-4').props('color=purple')
            with ui.card().classes('w-full gap-2'):
                ui.label("Actions:").classes(TITLE_CLASSES)
                build_run_view_actions()
            with ui.expansion('Run info', icon = 'info').classes('w-full gap-2'):
                # ui.label("Run info:").classes(TITLE_CLASSES)
                for column_name, conf in run.database_columns.items():
                    value = str(conf['value'])
                    if len(value) > 20 or value is None:
                        continue
                    if 'label' in conf:
                        label = ui.label(f"{conf['label']}: ")
                    else:
                        label = ui.label(f"{column_name.upper()}: ")
                    label.classes('font-semibold m-0 p-0"')
                    ui.label(value).classes("m-0 p-0 ml-5")

        with ui.column().classes('flex-1 min-w-0'):
            with ui.expansion('Plots', icon='stacked_line_chart', value=True)\
                .classes(EXPANSION_CLASSES):
                app.storage.tab["placeholders"]["plots"] = ui.row().\
                    classes('w-full min-h-[50vh] p-1 items-stretch')
                build_xarray_grid()

                    #.style('line-height: 1rem; padding-top: 0; padding-bottom: 0;')
            with ui.expansion('xarray summary', icon='summarize', value=False)\
                .classes(EXPANSION_CLASSES):
                build_xarray_html()
            with ui.expansion('analysis', icon='science', value=False)\
                .classes(EXPANSION_CLASSES):
                with ui.row():
                    ui.label("Working on it!  -Andi").classes(TITLE_CLASSES)
            with ui.expansion('metadata', icon='numbers', value=False)\
                .classes(f"{EXPANSION_CLASSES}  overflow-x-auto"):
                placeholder_metadata = {}
                placeholder_metadata['code'] = ui.code(
                    content = 'Placeholder for QUA program',
                    language = 'python')\
                    .classes('w-full overflow-x-auto whitespace-pre')
                ui.button(
                    icon = 'code',
                    text="load qua program",
                    on_click = lambda: load_qua_code(run, placeholder_metadata),
                )
                ui.button(
                    icon = 'download',
                    text="download serialized qua program",
                    on_click = lambda: download_qua_code(run),
                )

def add_dim_dropdown(sweep_idx: int):
    """
    Add a dropdown to select the dimension option for a given sweep index.

    Args:
        sweep_idx (int): Index of the sweep to add the dropdown for
    """
    run = app.storage.tab["run"]
    width = 'w-full'
    dim = run.sweep_dict[sweep_idx]
    local_placeholder = {"slider": None}
    dims_names = run.parallel_sweep_axes[sweep_idx]
    ui.radio(
        options = dims_names,
        value=dim.name,
        on_change = lambda e: update_sweep_dim_name(dim, e.value)
        ).classes(f"{width}  text-xs m-0 p-0").props('dense')
    ui_element = ui.select(
        options = AXIS_OPTIONS,
        value = str(dim.option),
        label = f'{dim.name.replace("__", ".")}',
        on_change = lambda e: update_dim_selection(
            dim, e.value, local_placeholder["slider"])
    ).classes(f"{width} text-sm m-0 p-0").props('dense')
    dim.ui_selector = ui_element
    local_placeholder["slider"] = ui.column().classes('w-full')
    if dim.option == 'select_value':
        build_dim_slider(run, dim)

def update_dim_selection(dim: Dim, value: str, slider_placeholder):
    """
    Update the dimension/sweep selection and rebuild the plot grid.

    Args:
        dim (Dim): The dimension object to update
        value (str): The new selection value
        slider_placeholder: The UI placeholder to update
    """
    run: BaseRun = app.storage.tab["run"]
    if dim.slider is not None:
        print("DELETING SLIDER")
        dim.slider.delete()
        dim.slider = None
        dim.select_label.delete()
        dim.select_label = None
    print(value)
    if value == 'select_value':
        with slider_placeholder:
            build_dim_slider(run, dim)
    run.update_subset_dims(dim, value)
    dim.option = value
    build_xarray_grid()

def build_dim_slider(run: BaseRun, dim: Dim):
    """
    Build a slider for selecting the index of a dimension.

    Args:
        dim (Dim): The dimension object
    """
    dim_size = run.full_data_set.sizes[dim.name]
    with ui.row().classes("w-full items-center"):
        with ui.column().classes('flex-grow'):
            dim.slider = ui.slider(
                min=0, max=dim_size - 1, step=1, value=0,
                on_change=lambda e: run.update_subset_dims(dim, 'select_value', e.value),
                ).classes('flex-grow')\
                .props('color="purple" markers')
        dim.select_label = ui.html('').classes(
            'shrink-0 text-right px-2 py-1 bg-purple text-white rounded-lg text-xs font-normal text-center')
        update_value_from_dim_slider(
            dim.select_label, dim.slider, dim, plot = False)
        dim.slider.on(
            'update:model-value',
            lambda e: update_value_from_dim_slider(dim.select_label, dim.slider, dim),
            throttle=0.2, leading_events=False)


def update_value_from_dim_slider(label, slider, dim: Dim, plot = True):
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
    if plot:
        build_xarray_grid()

def update_sweep_dim_name(dim: Dim, new_name: str):
    """
    Update the name of the dimension in the sweep dict and the dim object.
    
    Args:
        dim (Dim): The dimension object to update
        new_name (str): The new name for the dimension
    """
    dim.name = new_name
    dim.ui_selector.label = new_name.replace("__", ".")
    build_xarray_grid()

def load_qua_code(run: BaseRun, placeholder: dict):
    """Load and display the QUA code for the given run."""
    try:
        qua_code = run.get_qua_code(as_string = True)
        qua_code = qua_code.split("config = {")[0]
        placeholder['code'].set_content(qua_code)
    except Exception as e:
        ui.notify(f'Error loading QUA code: {str(e)}', type='negative')
        raise e

def download_qua_code(run: BaseRun) -> None:
    """Download the serialized QUA code for the given run."""
    try:
        qua_code_bytes = run.get_qua_code(as_string = False)
        ui.download(qua_code_bytes, 'test.py')
        #os.remove(file_name)
    except Exception as e:
        ui.notify(f'Error downloading QUA code: {str(e)}', type='negative')
        raise e

async def create_run(run_id: int) -> BaseRun:
    """Create a Run object for the given run ID."""
    if inspector.database_type == 'qcodes':
        run = QcodesRun(int(run_id))
    elif inspector.database_type == 'arbok_native':
        run = NativeRun(int(run_id))
    else:
        raise ValueError(
            "Database type must be 'qcodes' or 'arbok_native is:"
            f"{inspector.database_type}")
    await nicegui_run.io_bound(run.prepare_run)
    return run
