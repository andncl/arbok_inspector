"""
Run class representing a single run of the experiment.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from abc import ABC, abstractmethod
import ast
import re
import io
import json
from qcodes.dataset import load_by_id
from nicegui import ui, app
from nicegui import run as nicegui_run
import xarray as xr



from arbok_inspector.classes.dim import Dim
from arbok_inspector.widgets.build_xarray_grid import build_xarray_grid
from arbok_inspector.state import ArbokInspector, inspector

if TYPE_CHECKING:
    from qcodes.dataset.data_set import DataSet
    from xarray import Dataset

AXIS_OPTIONS = ['average', 'select_value', 'y-axis', 'x-axis']

class BaseRun(ABC):
    """
    Class representing a run with its data and methods
    """
    def __init__(self, run_id: int):
        """
        Constructor for Run class
        
        Args:
            run_id (int): ID of the run
        """
        self.run_id: int = run_id
        self.title: str = f'Run ID: {run_id}  (-> add experiment)'
        self.inspector: ArbokInspector =  inspector
        self.parallel_sweep_axes: dict = {}
        self.sweep_dict: dict[int, Dim] = {}
        self.full_data_set: Dataset | None = None
        self._database_columns: dict[str, dict[str, str]] = {}
        self.dims: list[Dim] = []
        self.plot_selection: list[str] = []
        self.last_avg_subset: Dataset | None = None

    @property
    def database_columns(self) -> dict[str, dict[str, str]]:
        """Column names of database, with their values and shown labels"""
        return self._database_columns

    @abstractmethod
    def _get_database_columns(self) -> dict[str, dict[str, str]]:
        pass

    @abstractmethod
    def _load_dataset(self) -> Dataset:
        """
        Load the dataset for the given run ID from the appropriate database type.
        
        Args:
            run_id (int): ID of the run
            database_type (str): Type of the database ('qcodes' or 'arbok')
        Returns:
            DataSet: Loaded dataset
        """
        pass

    @abstractmethod
    def get_qua_code(self, as_string: bool = False) -> str:
        """
        Retrieve the QUA code associated with this run.

        Returns:
            qua_code (str): The QUA code as a string
        """
        pass

    def prepare_run(self) -> None:
        """Prepare the run by loading the dataset asynchronously."""
        self._database_columns = self._get_database_columns()
        self.full_data_set: Dataset = self._load_dataset()
        self.process_run_data()

    def process_run_data(self) -> None:
        """
        Prepare the run by loading dataset and initializing attributes
        """
        self.last_avg_subset: Dataset = self.full_data_set
        self.load_sweep_dict()
        self.dims: list[Dim] = list(self.sweep_dict.values())
        self.dim_axis_option: dict[str, str|list[Dim]] = self.set_dim_axis_option()
        print(self.dims)

        self.plot_selection: list[str] = self.select_results_by_keywords(
            app.storage.general["result_keywords"]
        )
        print(f"Initial plot selection: {self.plot_selection}")
        self.plots_per_column: int = 2
        self.plots: list = []
        self.figures: list = []

    def load_sweep_dict(self):
        """
        Load the sweep dictionary from the dataset
        TODO: check metadata for sweep information!
        Returns:
            sweep_dict (dict): Dictionary with sweep information
            is_together (bool): True if all sweeps are together, False otherwise
        """
        self.parallel_sweep_axes = {}
        dims = self.full_data_set.dims
        for i, dim in enumerate(dims):
            dependent_coords = [
                name for name, coord in self.full_data_set.coords.items() if dim in coord.dims]
            self.parallel_sweep_axes[i] = dependent_coords
        self.sweep_dict = {
            i: Dim(names[0]) for i, names in self.parallel_sweep_axes.items()
            }
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
        options = {x: [] for x in AXIS_OPTIONS}
        print(f"Setting average to {app.storage.general['avg_axis']}")
        for dim in self.dims:
            if app.storage.general["avg_axis"] is None:
                break
            if app.storage.general["avg_axis"] in dim.name:
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

    def select_results_by_keywords(self, keywords: str) -> list[str]:
        """
        Select results by keywords in their name.
        Args:
            keywords (list): List of keywords to search for
        Returns:
            selected_results (list): List of selected result names

        TODO: simplify this! way too complicated
        """
        print(f"using keywords: {keywords}")
        try:
            if len(keywords) == 0:
                keywords = []
            else:
                keywords = ast.literal_eval(keywords)
        except (SyntaxError, ValueError):
            print(f"Error parsing keywords: {keywords}")
            keywords = []
            ui.notify(
                f"Error parsing result keywords: {keywords}. Please use a valid Python list.",
                color='red',
                position='top-right'
            )
        if not isinstance(keywords, list):
            keywords = [keywords]
        selected_results = []
        print(f"using keywords: {keywords}")
        for result in self.full_data_set.data_vars:
            for keyword in keywords:
                if isinstance(keyword, str) and keyword in str(result):
                    selected_results.append(result)
                elif isinstance(keyword, tuple) and all(
                        subkey in str(result) for subkey in keyword):
                    selected_results.append(result)
        selected_results = list(set(selected_results))  # Remove duplicates
        if len(selected_results) == 0:
            selected_results = [next(iter(self.full_data_set.data_vars))]
        print(f"Selected results: {selected_results}")
        return selected_results

    def update_subset_dims(self, dim: Dim, selection: str, index: int = 0):
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
                print(f"Removing {dim.name} from {option}")
                self.dim_axis_option[option].remove(dim)
                dim.option = None
                if option == 'select_value':
                    dim.select_index = 0
        if dim.option in ['x-axis', 'y-axis']:
            print(f"Removing {dim.name} from {dim.option}")
            self.dim_axis_option[dim.option] = None

        ### Now, set new option
        if selection in ['average', 'select_value']:
            # dim.ui_selector.value = selection
            dim.select_index = index
            self.dim_axis_option[selection].append(dim)
            return
        if selection in ['x-axis', 'y-axis']:
            old_dim = self.dim_axis_option[selection]
            self.dim_axis_option[selection] = dim
            if old_dim:
                # Set previous dim (having this option) to 'select_value'
                # Required since x and y axis have to be unique
                print(old_dim)
                print(f"Updating {old_dim.name} to {dim.name} on {selection}")
                if old_dim.option in ['x-axis', 'y-axis']:
                    self.dim_axis_option['select_value'].append(old_dim)
                    old_dim.option = 'select_value'
                    old_dim.ui_selector.value = 'select_value'
                    self.update_subset_dims(old_dim, 'select_value', old_dim.select_index)
        dim.ui_selector.update()

    def generate_subset(self, has_new_data: bool = False) -> Dataset:
        """
        Generate the subset of the full dataset based on the current dimension options.
        Returns:
            sub_set (xarray.Dataset): The subset of the full dataset
        """
        last_non_avg_dims = list(self.last_avg_subset.dims)
        avg_names = [d.name for d in self.dim_axis_option['average']]
        plot_names = [d.name for d in self.dim_axis_option['select_value']]
        if self.dim_axis_option['y-axis']:
            plot_names.append(self.dim_axis_option['y-axis'].name)
        plot_names.append(self.dim_axis_option['x-axis'].name)
        if set(plot_names) == set(last_non_avg_dims) and not has_new_data:
            sub_set = self.last_avg_subset
            print(f"Re-using last averaged subset: {list(sub_set.dims)}")
        else:
            print(f"Averiging over {avg_names}")
            sub_set = self.full_data_set.mean(dim=avg_names)
            self.update_select_sliders()
        self.last_avg_subset = sub_set
        sel_dict = {d.name: d.select_index for d in self.dim_axis_option['select_value']}
        print(f"Selecting subset with: {sel_dict}")
        sub_set = sub_set.isel(**sel_dict).squeeze()
        print("subset dimensions", list(sub_set.dims))
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
        build_xarray_grid(has_new_data=False)

    def update_select_sliders(self):
        """
        Update the select sliders based on the current dimension options.
        """
        for dim in self.dim_axis_option['select_value']:
            print(f"Updating slider for {dim.name}")
            dim.slider._props["max"] = len(self.full_data_set[dim.name]) - 1
            dim.slider.update()
