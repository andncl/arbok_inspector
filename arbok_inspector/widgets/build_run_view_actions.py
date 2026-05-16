"""Module containing function to build run-view options"""
from __future__ import annotations
from typing import TYPE_CHECKING
import os
import asyncio
from io import BytesIO

from nicegui import app, ui
from nicegui import run as nicegui_run

from arbok_inspector.classes.dim import Dim
from arbok_inspector.widgets.json_plot_settings_dialog import (
    JsonPlotSettingsDialog)
from arbok_inspector.widgets.build_xarray_grid import build_xarray_grid

if TYPE_CHECKING:
    from arbok_inspector.classes.base_run import BaseRun

DEFAULT_REFRESH_INTERVAL_S = 2

def build_run_view_actions() -> None:
    """Build the run view action buttons and controls."""
    with ui.column().classes('w-full items-stretch gap-2'):
        # Row 1: Update + Debug
        with ui.row().classes('w-full gap-1 flex-nowrap'):
            ui.button(
                'Update',
                icon='refresh',
                color='green',
                on_click=reload_dataset_and_refresh_plots
                ).props('dense size=sm').classes('flex-1 min-w-0')
            ui.button(
                'Debug', icon='info', color='red', on_click=print_debug
                ).props('dense size=sm').classes('flex-1 min-w-0')

        # Row 2: Settings buttons
        with ui.row().classes('w-full gap-1 flex-nowrap'):
            dialog_1d = JsonPlotSettingsDialog('plot_dict_1D')
            dialog_2d = JsonPlotSettingsDialog('plot_dict_2D')

            ui.button('1D JSON', color='pink',
                    on_click=dialog_1d.open).props('dense size=sm')\
                    .classes('flex-1 min-w-0')
            ui.button('2D JSON', color='orange',
                    on_click=dialog_2d.open).props('dense size=sm')\
                    .classes('flex-1 min-w-0')

        # Row 3: Timer controls
        with ui.row().classes('w-full items-center gap-1 flex-nowrap'):
            timer = ui.timer(
                interval=DEFAULT_REFRESH_INTERVAL_S,
                callback=reload_dataset_and_refresh_plots,
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
                value=2,
                format='%.0f',
                on_change=lambda e: set_plots_per_column(e.value),
            ).props('dense outlined').classes('flex-1 min-w-0 text-xs')

            ui.number(
                label='Font',
                value=app.storage.tab.get("plot_font_size", 12),
                min=4,
                max=40,
                step=1,
                format='%.0f',
                on_change=lambda e: set_plot_font_size(e.value),
            ).props('dense outlined').classes('flex-1 min-w-0 text-xs')

        # --- Row 5: Log scale toggles ---
        with ui.row().classes('w-full gap-1 items-center flex-nowrap'):
            ui.label('Log:').classes('text-xs')
            ui.switch(
                'X',
                value=app.storage.tab.get("log_scale_x", False),
                on_change=lambda e: set_log_scale('x', e.value),
            ).props('dense')
            ui.switch(
                'Y',
                value=app.storage.tab.get("log_scale_y", False),
                on_change=lambda e: set_log_scale('y', e.value),
            ).props('dense')

        # --- Row 6: Download buttons ---
        with ui.row().classes('w-full gap-1 flex-nowrap'):
            ui.button(
                'Full',
                icon='file_download',
                color='blue',
                on_click=download_full_dataset
                ).props('dense size=sm').classes('flex-1 min-w-0')
            ui.button(
                'Selec.',
                icon='file_download',
                color='darkblue',
                on_click=download_data_selection
                ).props('dense size=sm').classes('flex-1 min-w-0')

def on_interval_change(e, timer):
    try:
        value = float(e.value)
        if value < 0.1:
            ui.notify('Interval must be at least 0.1 s', color='red')
            e.sender.value = timer.interval  # revert
            return
        timer.interval = value
        ui.notify(f'Refresh interval set to {value:.2f} s', color='green')
    except ValueError:
        ui.notify('Please enter a valid number', color='red')
        e.sender.value = timer.interval  # revert

def set_plot_font_size(value: float):
    """Set the font size for plot axes and ticks, then rebuild plots."""
    size = int(value)
    app.storage.tab["plot_font_size"] = size
    ui.notify(f'Font size set to {size}', position='top-right')
    build_xarray_grid()

def set_log_scale(axis: str, value: bool):
    """Toggle log/linear scale for the given axis, then rebuild plots."""
    app.storage.tab[f"log_scale_{axis}"] = value
    scale = "log" if value else "linear"
    ui.notify(f'{axis.upper()}-axis scale set to {scale}', position='top-right')
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

def download_full_dataset():
    """Download the full dataset as a NetCDF file."""
    run = app.storage.tab["run"]
    netcfd_bytes = dataset_to_netcdf_bytes(run.full_data_set)
    ui.download(netcfd_bytes.getvalue(), f"{run.run_id}.nc")

def download_data_selection():
    """Download the current data selection as a NetCDF file."""
    run = app.storage.tab["run"]
    netcfd_bytes = dataset_to_netcdf_bytes(run.last_avg_subset)
    ui.download(netcfd_bytes.getvalue(), f"{run.run_id}_selection.nc")

def print_debug(run: BaseRun):
    """Print debugging information about the current run."""
    print("\nDebugging BaseRun:")
    run = app.storage.tab["run"]
    for key, val in run.dim_axis_option.items():
        if isinstance(val, list):
            val_str = str([d.name for d in val])
        elif isinstance(val, Dim):
            val_str = val.name
        else:
            val_str = str(val)
        print(f"{key}: \t {val_str}")

refresh_lock = asyncio.Lock()

async def reload_dataset_and_refresh_plots() -> None:
    """Reload the dataset and refresh the plots."""
    if refresh_lock.locked():
        return
    async with refresh_lock:
        run: BaseRun = app.storage.tab["run"]
        run.full_data_set = await nicegui_run.io_bound(run._load_dataset)
        ui.notify("Dataset reloaded", color='green')
        build_xarray_grid(has_new_data=True)

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
