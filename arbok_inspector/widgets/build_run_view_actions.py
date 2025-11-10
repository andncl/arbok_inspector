"""Module containing function to build run-view options"""
from __future__ import annotations
from typing import TYPE_CHECKING
import os
from nicegui import ui, app

from arbok_inspector.widgets.json_plot_settings_dialog import JsonPlotSettingsDialog
from arbok_inspector.widgets.build_xarray_grid import build_xarray_grid

if TYPE_CHECKING:
    from arbok_inspector.classes.dim import Dim
    from arbok_inspector.arbok_inspector.classes.base_run import BaseRun

def build_run_view_actions() -> None:
    with ui.column().classes():
        with ui.row():
            ui.button(
                text='Update ',
                icon='refresh',
                color='green',
                on_click=lambda: build_xarray_grid(),
            ).props('dense')

            ui.button(
                text='Debug',
                icon='info',
                color='red',
                on_click=lambda: print_debug(),
            ).classes('h-8 px-2').props('dense')
        with ui.row():
            dialog_1d = JsonPlotSettingsDialog('plot_dict_1D')
            dialog_2d = JsonPlotSettingsDialog('plot_dict_2D')

            ui.button(
                text='1D settings',
                color='pink',
                on_click=dialog_1d.open,
            ).props('dense')

            ui.button(
                text='2D settings',
                color='orange',
                on_click=dialog_2d.open,
            ).props('dense')

        ui.number(
            label='# per col',
            value=2,
            format='%.0f',
            on_change=lambda e: set_plots_per_column(e.value),
        ).props('dense outlined').classes('w-20 h-8 text-xs mb-2')
        with ui.row():
            ui.button(
                icon = 'file_download',
                text = 'full',
                color = 'blue',
                on_click=download_full_dataset,
            ).props('dense')
            ui.button(
                icon = 'file_download',
                text = 'selection',
                color='darkblue',
                on_click=download_data_selection,
            ).props('dense')

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
    local_path = f'./run_{run.run_id}.nc'
    run.full_data_set.to_netcdf(local_path)
    ui.download.file(local_path)
    os.remove(local_path)

def download_data_selection():
    """Download the current data selection as a NetCDF file."""
    run = app.storage.tab["run"]
    local_path = f'./run_{run.run_id}_selection.nc'
    run.last_subset.to_netcdf(local_path)
    ui.download.file(local_path)
    os.remove(local_path)

def print_debug(run: BaseRun):
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