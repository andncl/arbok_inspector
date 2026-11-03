"""Run view page showing the data and plots for a specific run"""
from __future__ import annotations
from typing import TYPE_CHECKING
import copy

from nicegui import ui, app
from nicegui import run as nicegui_run

from arbok_inspector.state import inspector
from arbok_inspector.run_session import RunSession, register_session
from arbok_inspector.widgets.build_xarray_grid import PlotGrid, request_plot_update
from arbok_inspector.widgets.build_xarray_html import build_xarray_html
from arbok_inspector.widgets.build_run_view_actions import build_run_view_actions
from arbok_inspector.widgets.dim_widget import DimWidget
from arbok_inspector.classes.dim import AXIS_OPTIONS
from arbok_inspector.classes.qcodes_run import QcodesRun
from arbok_inspector.classes.native_run import NativeRun

if TYPE_CHECKING:
    from arbok_inspector.classes.dim import Dim
    from arbok_inspector.classes.base_run import BaseRun

EXPANSION_CLASSES = 'w-full p-0 gap-1 border border-gray-400 rounded-lg no-wrap items-start pt-0 mt-0'
TITLE_CLASSES = 'text-lg font-semibold'


@ui.page('/run/{run_id}')
async def run_page(run_id: str):
    """Page showing the details and plots for a specific run."""
    ui.page_title(f"{run_id}")
    run_id = int(run_id)
    _ = await ui.context.client.connected()

    if inspector.database_type is None:
        with ui.column().classes('absolute-center items-center gap-4'):
            ui.icon('warning', color='orange', size='xl')
            ui.label('No database connected').classes('text-xl')
            ui.button('Go to connection page', icon='home',
                      on_click=lambda: ui.navigate.to('/'))
        return

    with ui.dialog() as loading_dialog:
        with ui.card().classes('p-6 items-center'):
            ui.label('Loading dataset...')
            ui.spinner(size='lg')
    loading_dialog.open()
    try:
        run = await create_run(run_id)
    except Exception as e:
        loading_dialog.close()
        ui.notify(f"Error loading run: {e}", type="negative", close_button="OK")
        ui.label(f"Failed to load run! {run_id}")
        raise e
    finally:
        if loading_dialog.visible:
            loading_dialog.close()

    session = RunSession(run=run, settings=_default_settings())
    register_session(session)
    dim_widgets = session.dim_widgets
    run.set_on_dim_changed(lambda dim: _on_dim_changed(dim, dim_widgets))

    with ui.row().classes('w-full gap-4'):
        with ui.column().classes('flex-none w-min'):
            with ui.card().classes('w-full gap-0 p-2'):
                ui.label(f'Run-ID: {run_id}').classes('text-2xl font-bold')
            with ui.card().classes('w-full gap-2'):
                ui.label("Coordinates:").classes('text-lg font-semibold pl-2')
                ui.toggle(
                    options=['Average', 'histogram'],
                    value='Average',
                    on_change=lambda e: toggle_statistics(e.value, run)
                ).classes('w-full').props('toggle-color=purple')
                ui.separator().classes('w-full my-1')
                for i, _ in run.parallel_sweep_axes.items():
                    add_dim_dropdown(run, sweep_idx=i, dim_widgets=dim_widgets)
            with ui.card().classes('w-full gap-2'):
                ui.label("Results:").classes(TITLE_CLASSES)
                for i, result in enumerate(run.full_data_set):
                    value = result in run.plot_selection
                    ui.checkbox(
                        text=result.replace("__", "."),
                        value=value,
                        on_change=lambda e, r=result: _on_plot_selection_change(run, e.value, r),
                    ).classes('text-sm h-4').props('color=purple')
            with ui.card().classes('w-full gap-2').style('max-width: 200px'):
                ui.label("Actions:").classes(TITLE_CLASSES)
                build_run_view_actions(session)
            with ui.expansion('Run info', icon='info').classes('w-full gap-2'):
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
            with ui.expansion(f'plot: {run.name}', icon='stacked_line_chart', value=True)\
                .classes(EXPANSION_CLASSES):
                session.plot_grid = PlotGrid(
                    session,
                    on_reloaded=lambda: _on_sliders_need_update(run, dim_widgets))
                session.plot_grid.request()
            with ui.expansion('xarray summary', icon='summarize', value=False)\
                .classes(EXPANSION_CLASSES):
                build_xarray_html(run)
            with ui.expansion('analysis', icon='science', value=False)\
                .classes(EXPANSION_CLASSES):
                with ui.row():
                    ui.label("Working on it!  -Andi").classes(TITLE_CLASSES)
            with ui.expansion('metadata', icon='numbers', value=False)\
                .classes(f"{EXPANSION_CLASSES}  overflow-x-auto"):
                placeholder_metadata = {}
                placeholder_metadata['code'] = ui.code(
                    content='Placeholder for QUA program',
                    language='python')\
                    .classes('w-full overflow-x-auto whitespace-pre')
                ui.button(
                    icon='code',
                    text="load qua program",
                    on_click=lambda: load_qua_code(run, placeholder_metadata),
                )
                ui.button(
                    icon='download',
                    text="download serialized qua program",
                    on_click=lambda: download_qua_code(run),
                )


def _default_settings() -> dict:
    """Tab-local plot settings, initialised from the cross-tab plot templates."""
    return {
        "plot_font_size": 12,
        "log_scale_x": False,
        "log_scale_y": False,
        "log_scale_z": False,
        "show_gridlines": True,
        "plot_dict_1D": copy.deepcopy(app.storage.general["plot_dict_1D"]),
        "plot_dict_2D": copy.deepcopy(app.storage.general["plot_dict_2D"]),
    }


def _on_dim_changed(dim: Dim, dim_widgets: dict[str, DimWidget]):
    """Callback: sync UI selector when BaseRun changes a dim's option."""
    dw = dim_widgets.get(dim.name)
    if dw:
        dw.sync_selector_to_dim()


def _on_sliders_need_update(run: BaseRun, dim_widgets: dict[str, DimWidget]):
    """Callback: update slider max values after the dataset was reloaded."""
    for dim in run.dim_axis_option['select_value']:
        dw = dim_widgets.get(dim.name)
        if dw:
            max_val = len(run.full_data_set[dim.name]) - 1
            dw.update_slider_max(max_val)


def _on_plot_selection_change(run: BaseRun, value: bool, readout_name: str):
    """Handle result checkbox toggle."""
    pretty_name = readout_name.replace("__", ".")
    run.update_plot_selection(value, readout_name)
    if readout_name in run.plot_selection:
        ui.notify(f'Result {pretty_name} added to plot selection', position='top-right')
    else:
        ui.notify(f'Result {pretty_name} removed from plot selection', position='top-right')
    request_plot_update()


def toggle_statistics(value: str, run: BaseRun):
    """Toggle between average and histogram display modes."""
    if value == 'Average':
        if run.show_histogram:
            avg_keyword = app.storage.general["avg_axis"]
            dim_to_y = None
            for avg_dim in run.dim_axis_option['average']:
                if avg_keyword not in avg_dim.name:
                    dim_to_y = avg_dim
                    run.update_subset_dims(dim_to_y, 'y-axis')
                    break
            if dim_to_y is None:
                if run.dim_axis_option['select_value']:
                    dim_to_y = run.dim_axis_option['select_value'][0]
                    run.update_subset_dims(dim_to_y, 'y-axis')
        run.show_histogram = False
    elif value == 'histogram':
        if run.show_fft or run.show_decay:
            ui.notify('Cannot enable histogram while FFT or decay is active. '
                      'Please remove the FFT/decay dimension first.', type='warning')
            return
        if not run.show_histogram:
            dim_to_bin = run.dim_axis_option['y-axis']
            if dim_to_bin:
                run.update_subset_dims(dim_to_bin, 'average')
        run.show_histogram = True
    request_plot_update()


def add_dim_dropdown(run: BaseRun, sweep_idx: int, dim_widgets: dict[str, DimWidget]):
    """Add a dropdown to select the dimension option for a given sweep index."""
    dim = run.sweep_dict[sweep_idx]
    dw = DimWidget(dim)
    dim_widgets[dim.name] = dw

    dims_names = run.parallel_sweep_axes[sweep_idx]
    ui.radio(
        options=dims_names,
        value=dim.name,
        on_change=lambda e: _update_sweep_dim_name(run, dim, e.value, dw, dim_widgets)
    ).classes('w-full text-xs m-0 p-0').props('dense')

    ui_element = ui.select(
        options=AXIS_OPTIONS,
        value=str(dim.option),
        label=f'{dim.name.replace("__", ".")}',
        on_change=lambda e: _update_dim_selection(run, dim, dw, e.value)
    ).classes('w-full text-sm m-0 p-0').props('dense')
    dw.selector = ui_element

    dw.slider_container = ui.column().classes('w-full')
    if dim.option == 'select_value':
        with dw.slider_container:
            dw.build_slider(run, on_plot=request_plot_update)
    elif dim.option == 'fft':
        with dw.slider_container:
            dw.build_fft_controls(run, on_plot=request_plot_update)
    elif dim.option == 'decay':
        with dw.slider_container:
            dw.build_decay_controls(run, on_plot=request_plot_update)


def _transform_conflict(run: BaseRun, dim: Dim, value: str) -> str | None:
    """Warning text if `value` would combine FFT, decay or histogram, else None."""
    def held_by_other(role: str) -> bool:
        return run.dim_axis_option.get(role) not in (None, dim)
    if value == 'decay' and (held_by_other('fft') or run.show_histogram):
        return 'Cannot use decay together with FFT or histogram.'
    if value == 'fft' and held_by_other('decay'):
        return 'Cannot use FFT together with decay.'
    return None


def _update_dim_selection(run: BaseRun, dim: Dim, dw: DimWidget, value: str):
    """Handle dimension role dropdown change."""
    conflict = _transform_conflict(run, dim, value)
    if conflict is not None:
        ui.notify(conflict, type='warning')
        dw.sync_selector_to_dim()
        return
    dw.delete_slider()
    dw.delete_fft_controls()
    dw.delete_decay_controls()
    if value == 'select_value' and dw.slider_container:
        with dw.slider_container:
            dw.build_slider(run, on_plot=request_plot_update)
    if value == 'fft' and dw.slider_container:
        with dw.slider_container:
            dw.build_fft_controls(run, on_plot=request_plot_update)
    if value == 'decay' and dw.slider_container:
        with dw.slider_container:
            dw.build_decay_controls(run, on_plot=request_plot_update)
    if value == 'y-axis' and run.show_histogram:
        ui.notify('Cannot set dimension as y-axis while histogram is enabled. '
                  'Please disable histogram first.', type='warning')
        return
    run.update_subset_dims(dim, value)
    dim.option = value
    request_plot_update()


def _update_sweep_dim_name(run: BaseRun, dim: Dim, new_name: str,
                           dw: DimWidget, dim_widgets: dict[str, DimWidget]):
    """Update the dimension name when the user picks a parallel coordinate."""
    old_name = dim.name
    dim.name = new_name
    dw.sync_label_to_dim()
    if old_name in dim_widgets:
        del dim_widgets[old_name]
    dim_widgets[new_name] = dw
    request_plot_update()


def load_qua_code(run: BaseRun, placeholder: dict):
    """Load and display the QUA code for the given run."""
    try:
        qua_code = run.get_qua_code(as_string=True)
        qua_code = qua_code.split("config = {")[0]
        placeholder['code'].set_content(qua_code)
    except Exception as e:
        ui.notify(f'Error loading QUA code: {str(e)}', type='negative')
        raise e


def download_qua_code(run: BaseRun) -> None:
    """Download the serialized QUA code for the given run."""
    try:
        qua_code_bytes = run.get_qua_code(as_string=False)
        ui.download(qua_code_bytes, 'test.py')
    except Exception as e:
        ui.notify(f'Error downloading QUA code: {str(e)}', type='negative')
        raise e


async def create_run(run_id: int) -> BaseRun:
    """Create a Run object for the given run ID."""
    if inspector.database_type == 'qcodes':
        run = QcodesRun(int(run_id))
    elif inspector.database_type == 'native_arbok':
        run = NativeRun(int(run_id))
    else:
        raise ValueError(
            "Database type must be 'qcodes' or 'native_arbok', is: "
            f"{inspector.database_type}")
    await nicegui_run.io_bound(
        run.prepare_run,
        avg_axis=app.storage.general.get("avg_axis"),
        result_keywords=app.storage.general.get("result_keywords", ""),
    )
    return run
