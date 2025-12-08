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
    with ui.column().classes('items-start'):  # compact vertical layout
        # Row 1: Update + Debug
        with ui.row().classes('gap-2'):
            ui.button(
                'Update',
                icon='refresh',
                color='green',
                on_click=reload_dataset_and_refresh_plots
                ).props('dense')
            ui.button(
                'Debug', icon='info', color='red', on_click=print_debug
                ).props('dense')

        # Row 2: Settings buttons
        with ui.row().classes('gap-2'):
            dialog_1d = JsonPlotSettingsDialog('plot_dict_1D')
            dialog_2d = JsonPlotSettingsDialog('plot_dict_2D')

            ui.button('1D settings', color='pink',
                    on_click=dialog_1d.open).props('dense')
            ui.button('2D settings', color='orange',
                    on_click=dialog_2d.open).props('dense')

        # Row 3: Timer controls
        with ui.row().classes('items-center gap-2'):
            timer = ui.timer(
                interval=DEFAULT_REFRESH_INTERVAL_S,
                callback=reload_dataset_and_refresh_plots,
                active=False
                )
            ui.label('Auto-plot')
            ui.switch(
                on_change=lambda e: setattr(timer, 'active', e.value)
            )
            ui.number(
                # label='(s)',
                value=DEFAULT_REFRESH_INTERVAL_S,
                min=0.1,
                step=0.1,
                format='%.1f',
                on_change=lambda e: on_interval_change(e, timer),
            ).props('dense suffix="s"').classes('w-12')
        # --- Row 4: Plot layout control ---
        with ui.row().classes('gap-2'):
            ui.number(
                label='# per col',
                value=2,
                format='%.0f',
                on_change=lambda e: set_plots_per_column(e.value),
            ).props('dense outlined').classes('w-24 h-8 text-xs')

        # --- Row 5: Download buttons ---
        with ui.row().classes('gap-2'):
            ui.button(
                'Full',
                icon='file_download',
                color='blue',
                on_click=download_full_dataset
                ).props('dense')
            ui.button(
                'Selection',
                icon='file_download',
                color='darkblue',
                on_click=download_data_selection
                ).props('dense')

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
