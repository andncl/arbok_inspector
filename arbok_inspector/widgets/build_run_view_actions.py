"""Module containing function to build run-view options"""
from __future__ import annotations
from typing import TYPE_CHECKING
from io import BytesIO

import xarray as xr

from nicegui import ui
from nicegui import json as nicegui_json
from nicegui import run as nicegui_run

from arbok_inspector.classes.dim import Dim
from arbok_inspector.widgets.json_plot_settings_dialog import (
    JsonPlotSettingsDialog)
from arbok_inspector.widgets.build_xarray_grid import request_plot_update
from arbok_inspector.helpers.figure_builder import DEFAULT_FONT_SIZE, FONT_SIZE_STEP
from arbok_inspector.helpers.code_snippet import python_snippet
from arbok_inspector.analysis.ridge import ridge_csv

if TYPE_CHECKING:
    from arbok_inspector.run_session import RunSession

DEFAULT_REFRESH_INTERVAL_S = 2

def build_run_view_actions(session: RunSession) -> None:
    """Build the run view action buttons and controls."""
    settings = session.settings
    with ui.column().classes('w-full items-stretch gap-2'):
        # Row 1: Update + Debug
        with ui.row().classes('w-full gap-1 flex-nowrap'):
            ui.button(
                'Update',
                icon='refresh',
                color='green',
                on_click=lambda: reload_dataset_and_refresh_plots(session)
                ).props('dense size=sm').classes('flex-1 min-w-0')
            ui.button(
                'Debug', icon='info', color='red',
                on_click=lambda: print_debug(session)
                ).props('dense size=sm').classes('flex-1 min-w-0')

        # Row 2: Settings buttons
        with ui.row().classes('w-full gap-1 flex-nowrap'):
            dialog_1d = JsonPlotSettingsDialog(
                'plot_dict_1D', storage=settings, on_apply=request_plot_update)
            dialog_2d = JsonPlotSettingsDialog(
                'plot_dict_2D', storage=settings, on_apply=request_plot_update)

            ui.button('1D JSON', color='pink',
                    on_click=dialog_1d.open).props('dense size=sm')\
                    .classes('flex-1 min-w-0')
            ui.button('2D JSON', color='orange',
                    on_click=dialog_2d.open).props('dense size=sm')\
                    .classes('flex-1 min-w-0')

        # Row 3: Timer controls
        with ui.row().classes('w-full items-center gap-1 flex-nowrap'):
            async def auto_reload() -> None:
                # Awaiting the render keeps timer ticks from overlapping
                await reload_dataset_and_refresh_plots(session, notify=False)
            timer = ui.timer(
                interval=DEFAULT_REFRESH_INTERVAL_S,
                callback=auto_reload,
                active=False
                )
            ui.label('Reload').classes('text-xs')
            ui.switch(
                on_change=lambda e: setattr(timer, 'active', e.value)
            ).props('dense')
            ui.number(
                value=DEFAULT_REFRESH_INTERVAL_S,
                min=0.1,
                step=0.1,
                format='%.1f',
                on_change=lambda e: on_interval_change(e, timer),
            ).props('dense suffix="s"').classes('flex-1 min-w-0')
        # --- Row 4: Plot layout control ---
        with ui.row().classes('w-full gap-1 flex-nowrap'):
            ui.number(
                label='# col',
                value=session.run.plots_per_column,
                min=1,
                format='%.0f',
                on_change=lambda e: set_plots_per_column(session, e.value),
            ).props('dense outlined').classes('flex-1 min-w-0 text-xs')

            ui.number(
                label='Font',
                value=settings.get("plot_font_size", DEFAULT_FONT_SIZE),
                # browsers step from `min`: keep min/max on the default's step grid
                min=5,
                max=39,
                step=FONT_SIZE_STEP,
                format='%.0f',
                on_change=lambda e: set_plot_font_size(session, e.value),
            ).props('dense outlined').classes('flex-1 min-w-0 text-xs')

        # --- Row 5: Log scale toggles ---
        with ui.row().classes('w-full gap-1 items-center flex-nowrap'):
            ui.label('Log:').classes('text-xs')
            for axis in ('x', 'y', 'z'):
                ui.switch(
                    axis.upper(),
                    value=settings.get(f"log_scale_{axis}", False),
                    on_change=lambda e, a=axis: set_log_scale(session, a, e.value),
                ).props('dense')

        # --- Row 6: Download buttons gridline toggle ---
        with ui.row().classes('w-full gap-1 flex-nowrap'):
            ui.button(
                'Full',
                icon='file_download',
                color='blue',
                on_click=lambda: download_full_dataset(session)
                ).props('dense size=sm').classes('flex-1 min-w-0')
            ui.button(
                'Selec.',
                icon='file_download',
                color='darkblue',
                on_click=lambda: download_data_selection(session)
                ).props('dense size=sm').classes('flex-1 min-w-0')
        # --- Row 7b :gridline toggle ---
        with ui.row().classes('w-full gap-1 flex-nowrap'):
            ui.label('Grid:').classes('text-xs')
            ui.switch(
                value=settings.get("show_gridlines", True),
                on_change=lambda e: toggle_gridlines(session, e.value),
            ).props('dense')
        # --- Row 8: ridge readout (FFT / decay) ---
        with ui.row().classes('w-full gap-1 items-center flex-nowrap'):
            ui.label('Ridge:').classes('text-xs')
            ui.switch(
                value=settings.get("show_ridge", False),
                on_change=lambda e: set_plot_setting(session, "show_ridge", e.value),
            ).props('dense').tooltip('Mark the brightest point of FFT / decay spectra')
            ui.button(
                'CSV', icon='file_download', color='teal',
                on_click=lambda: download_ridge_csv(session),
                ).props('dense size=sm').classes('flex-1 min-w-0')\
                .tooltip('Download the ridge positions')
        # --- Row 9: colour range ---
        with ui.row().classes('w-full gap-1 items-center flex-nowrap'):
            ui.label('Z:').classes('text-xs')
            z_mode = ui.toggle(
                {'auto': 'auto', 'percentile': '1–99%', 'manual': 'set'},
                value=settings.get("z_range_mode", "auto"),
                on_change=lambda e: set_plot_setting(session, "z_range_mode", e.value),
            ).props('dense size=sm no-caps toggle-color=purple')
        with ui.row().classes('w-full gap-1 flex-nowrap') as manual_range:
            for bound in ('min', 'max'):
                ui.number(
                    label=f'z {bound}',
                    value=settings.get(f"z_{bound}"),
                    on_change=lambda e, b=bound: set_plot_setting(session, f"z_{b}", e.value),
                ).props('dense outlined').classes('flex-1 min-w-0 text-xs')
        manual_range.bind_visibility_from(z_mode, 'value', value='manual')
        # --- Row 10: image export format + Python snippet ---
        with ui.row().classes('w-full gap-1 items-center flex-nowrap'):
            ui.toggle(
                {'svg': 'SVG', 'png': 'PNG'},
                value=settings.get("export_format", "svg"),
                on_change=lambda e: set_plot_setting(session, "export_format", e.value),
            ).props('dense size=sm no-caps toggle-color=purple')\
                .tooltip('Format of the camera button in the plot toolbar')
            snippet_dialog = PythonSnippetDialog()
            ui.button(
                'Python', icon='code', color='indigo',
                on_click=lambda: snippet_dialog.show(session),
                ).props('dense size=sm').classes('flex-1 min-w-0')\
                .tooltip('Python code reproducing this view')
        with ui.row().classes('w-full gap-1 flex-nowrap'):
            ui.button(
                'Plot JSON', icon='data_object', color='indigo',
                on_click=lambda: download_plot_json(session),
                ).props('dense size=sm').classes('flex-1 min-w-0')\
                .tooltip('Download the plotted figures as plotly JSON, e.g. for an LLM')

def on_interval_change(e, timer):
    try:
        value = float(e.value)
        if value < 0.1:
            ui.notify('Interval must be at least 0.1 s', color='red')
            e.sender.value = timer.interval  # revert
            return
        timer.interval = value
        ui.notify(f'Refresh interval set to {value:.2f} s', color='green')
    except (TypeError, ValueError):
        ui.notify('Please enter a valid number', color='red')
        e.sender.value = timer.interval  # revert

def set_plot_font_size(session: RunSession, value: float):
    """Set the font size for plot axes and ticks, then rebuild plots."""
    if value is None:
        return
    size = int(value)
    session.settings["plot_font_size"] = size
    ui.notify(f'Font size set to {size}', position='top-right')
    request_plot_update()

def set_plot_setting(session: RunSession, key: str, value) -> None:
    """Store a tab-local plot setting and rebuild the plots."""
    session.settings[key] = value
    request_plot_update()

def download_ridge_csv(session: RunSession):
    """Download the ridge positions (brightest point of FFT / decay spectra)."""
    csv = ridge_csv(session.run.last_subset or {})
    if csv is None:
        ui.notify('Ridge readout needs an FFT or decay dimension', type='warning')
        return
    ui.download(csv.encode(), f"{session.run.run_id}_ridge.csv")

async def download_plot_json(session: RunSession):
    """Download every plotted figure as a plotly JSON file (one file per plot)."""
    exports = session.plot_grid.exports if session.plot_grid is not None else []
    if not exports:
        ui.notify('Nothing plotted yet', type='warning')
        return
    for name, figure in exports:
        content = await nicegui_run.io_bound(nicegui_json.dumps, figure)
        ui.download(content.encode(), f"{name}.json", media_type='application/json')

class PythonSnippetDialog:
    """Dialog showing (and copying) Python code that reproduces the view."""

    def __init__(self):
        with ui.dialog() as self.dialog, ui.card().classes('max-w-[90vw]'):
            ui.label('Reproduce this view in Python').classes('text-lg font-semibold')
            self.code = ui.code('', language='python').classes('w-full')
            ui.button('Close', on_click=self.dialog.close).props('dense')

    def show(self, session: RunSession) -> None:
        run = session.run
        self.code.set_content(python_snippet(run, run.snapshot_view()))
        self.dialog.open()

def toggle_gridlines(session: RunSession, value: bool):
    """Toggle gridlines on/off for all plots, then rebuild."""
    session.settings["show_gridlines"] = value
    ui.notify(f'Gridlines {"on" if value else "off"}', position='top-right')
    request_plot_update()

def set_log_scale(session: RunSession, axis: str, value: bool):
    """Toggle log/linear scale for the given axis, then rebuild plots."""
    session.settings[f"log_scale_{axis}"] = value
    scale = "log" if value else "linear"
    ui.notify(f'{axis.upper()}-axis scale set to {scale}', position='top-right')
    request_plot_update()

def set_plots_per_column(session: RunSession, value: int):
    """
    Set the number of plots to display per column.

    Args:
        session: Session of the current tab
        value (int): The number of plots per column
    """
    if value is None or int(value) < 1:
        return
    ui.notify(f'Setting plots per column to {int(value)}', position='top-right')
    session.run.plots_per_column = int(value)
    request_plot_update()

async def download_full_dataset(session: RunSession):
    """Download the full dataset as a NetCDF file."""
    run = session.run
    netcdf_bytes = await nicegui_run.io_bound(
        dataset_to_netcdf_bytes, run.full_data_set)
    ui.download(netcdf_bytes.getvalue(), f"{run.run_id}.nc")

async def download_data_selection(session: RunSession):
    """Download the currently plotted data selection as a NetCDF file."""
    run = session.run
    if not run.last_subset:
        ui.notify('Nothing plotted yet', type='warning')
        return
    netcdf_bytes = await nicegui_run.io_bound(
        dataset_to_netcdf_bytes, xr.Dataset(run.last_subset))
    ui.download(netcdf_bytes.getvalue(), f"{run.run_id}_selection.nc")

def print_debug(session: RunSession):
    """Print debugging information about the current run."""
    print("\nDebugging BaseRun:")
    for key, val in session.run.dim_axis_option.items():
        if isinstance(val, list):
            val_str = str([d.name for d in val])
        elif isinstance(val, Dim):
            val_str = val.name
        else:
            val_str = str(val)
        print(f"{key}: \t {val_str}")

async def reload_dataset_and_refresh_plots(
        session: RunSession, notify: bool = True) -> None:
    """Reload the dataset and refresh the plots of this tab."""
    if session.plot_grid is None:
        return
    await session.plot_grid.refresh(reload=True)
    if notify:
        ui.notify("Dataset reloaded", color='green')

def dataset_to_netcdf_bytes(ds: xr.Dataset) -> BytesIO:
    """
    Convert an xarray Dataset to an in-memory NetCDF file (BytesIO)
    using zlib compression.

    Args:
        ds (xr.Dataset): The xarray Dataset to convert.
    Returns:
        BytesIO: In-memory bytes buffer containing the NetCDF data.
    """
    buffer = BytesIO()
    ds.to_netcdf(
        buffer,
        mode="w",
        # format="NETCDF4",
        # engine="netcdf4",
    )
    buffer.seek(0)
    return buffer
