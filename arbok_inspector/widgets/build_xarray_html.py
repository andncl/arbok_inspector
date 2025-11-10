"""
Build and display xarray dataset HTML with dark theme.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from nicegui import ui, app

if TYPE_CHECKING:
    from arbok_inspector.arbok_inspector.classes.base_run import BaseRun
    from xarray import Dataset

def build_xarray_html():
    """Display the xarray dataset in a dark-themed style."""
    run: BaseRun = app.storage.tab["run"]
    ds: Dataset = run.full_data_set
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