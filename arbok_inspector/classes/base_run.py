"""
Run class representing a single run of the experiment.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from abc import ABC, abstractmethod
import ast
from nicegui import ui, app

from arbok_inspector.classes.dim import Dim
from arbok_inspector.widgets.build_xarray_grid import build_xarray_grid
from arbok_inspector.state import ArbokInspector, inspector

if TYPE_CHECKING:
    from xarray import Dataset

AXIS_OPTIONS = ['average', 'select_value', 'y-axis', 'x-axis']

class BaseRun(ABC):
    """
    Class representing a run with its data and methods
    """
    full_data_set: Dataset
    last_avg_subset: Dataset
    name: str

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
        self._database_columns: dict[str, dict[str, str]] = {}
        self.dims: list[Dim] = []
        self.plot_selection: list[str] = []
        self.last_avg_subset: Dataset | None = None
        self.result_axes: dict[str, dict[str, list[Dim]]] = {}  # {result_var: {type: [dim]}}

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
        # self.dim_axis_option: dict[str, Dim|list[Dim]] = self.set_dim_axis_option()
        # self.result_axes = self.set_dim_axis_option()
        self.set_dim_axis_option()
        print("result_axis", self.result_axes)
        print("self.dims", self.dims)

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
            options (dict): Dictionary with keys 'average', 'select_value', 'x-axis' and 'y-axis'
        """

        print(f"Setting average to {app.storage.general['avg_axis']}")
        print("total_optiosn", self.full_data_set.data_vars.keys())
        print("app store", app.storage.general["avg_axis"])

        # Populate per-result axis assignments.
        # Each result gets its own x/y from its own dims, ignoring averaged ones.
        # avg_names = {d.name for d in options['average']}
        for var_name in self.full_data_set.data_vars.keys():
            var_name = str(var_name)  # for type stability
            print(var_name)
            self.result_axes[var_name] = {}
            var_dims = list(self.full_data_set[var_name].dims)
            print("--> ", var_dims)

            # Remove any dims that should be averaged
            # if app.storage.general["avg_axis"]:
            #     for dim in var_dims:

            available = [d for d in self.dims if d.name in var_dims]
            if len(available) >= 2:
                y_axis = available.pop(-2)
                y_axis.option = "y-axis"

                x_axis = available.pop(-1)
                x_axis.option = "x-axis"

                for dim in available:
                    dim.option = "select_value"
                    dim.select_index = 0

                self.result_axes[var_name] =  {
                    'x-axis': [x_axis],
                    'y-axis': [y_axis],
                    "average": [],
                    "select_value": available
                }
            elif len(available) == 1:
                x_axis = available.pop(-1)
                x_axis.option = "x-axis"
                self.result_axes[var_name] = {
                    "x-axis": [x_axis],
                    "y-axis": [],
                    "average": [],
                    "select_value": []
                }
            else:
                print("WHAAA????", available)



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
        print("All dims: ", self.result_axes)
        for result, axes in self.result_axes.items():
            for option in AXIS_OPTIONS:
                if axes[option] is not None and dim in axes[option]:
                    print(f"Removing {result}/{dim.name} from {option}")
                    self.result_axes[result][option].remove(dim)
                    # if len(self.result_axes[result][option]) == 0:
                    #     self.result_axes[result][option] = None
                    dim.option = None
                    if option == 'select_value':
                        dim.select_index = 0  # reset

        # Find ALL results that contain this dim
        matching_results = [
            str(result_name)
            for result_name, da in self.full_data_set.items()
            if dim.name in da.dims
        ]
        print("--> found in", matching_results)
        if not matching_results:
            print("Couldn't find dimension in any result")
            return

        ### Now, set new option for every result containing this dim
        if selection in ['average', 'select_value']:
            dim.select_index = index
            for result_dim in matching_results:
                self.result_axes[result_dim][selection].append(dim)
        if selection in ['x-axis', 'y-axis']:
            displaced_dims = set()
            for result_dim in matching_results:
                if self.result_axes[result_dim][selection]:
                    old_dim = self.result_axes[result_dim][selection][0]
                else:
                    old_dim = None
                self.result_axes[result_dim][selection] = [dim]
                if old_dim and old_dim is not dim and old_dim not in displaced_dims:
                    displaced_dims.add(old_dim)
                    old_dim.option = "select_value"
                    old_dim.ui_selector.value = 'select_value'
                    print(f"Updating clash of {result_dim}/{old_dim.name} to {result_dim}/{dim.name} on {selection}")
                    self.update_subset_dims(old_dim, 'select_value', old_dim.select_index)
        dim.ui_selector.update()

    def update_result_axis(self, result_name: str, axis: str, dim_name: str | None) -> None:
        """
        Set the x-axis or y-axis for a specific result variable and rebuild plots.

        Args:
            result_name: Name of the result variable.
            axis: Either 'x-axis' or 'y-axis'.
            dim_name: Dimension name to assign, or None to clear.
        """
        if result_name not in self.result_axes:
            self.result_axes[result_name] = {x: [] for x in AXIS_OPTIONS}
        dim = next((d for d in self.dims if d.name == dim_name), [])
        self.result_axes[result_name][axis] = [dim] if dim is not None else []
        print("reaching through update_result_axis")
        build_xarray_grid()

    def _get_averaged_subset(self, has_new_data: bool = False) -> Dataset:
        """
        Return the dataset averaged over all 'average'-role dimensions.

        Re-uses the cached ``last_avg_subset`` when the set of non-averaged
        dimensions has not changed and no new data was signalled.

        Args:
            has_new_data: Force re-computation even if the dim config is unchanged.
        Returns:
            xr.Dataset with 'average' dimensions collapsed.
        """
        last_non_avg_dims = list(self.last_avg_subset.dims)
        avg_names = []
        expected_remaining = []
        for dims in self.result_axes.values():
            if dims is not None:
                avg_names.extend([d.name for d in dims['average']])
                expected_remaining.extend([d.name for d in dims['select_value']])
            for ax in (dims['x-axis'] + dims['y-axis']):
                if ax is not None:
                    expected_remaining.append(ax.name)
        print("avg_names:", avg_names)
        print("expected_remaining:", expected_remaining)
        if set(expected_remaining) == set(last_non_avg_dims) and not has_new_data:
            print(f"Re-using cached averaged subset: {last_non_avg_dims}")
            return self.last_avg_subset
        print(f"Averaging over {avg_names}")
        sub_set = self.full_data_set.mean(dim=avg_names)
        self.update_select_sliders()
        self.last_avg_subset = sub_set
        return sub_set

    # def generate_subset(self, has_new_data: bool = False) -> Dataset:
    #     """
    #     Generate the subset of the full dataset based on the current dimension options.
    #     Returns:
    #         sub_set (xarray.Dataset): The subset of the full dataset
    #     """
    #     avg_sub = self._get_averaged_subset(has_new_data=has_new_data)
    #     sel_dict = {d.name: d.select_index for d in self.dim_axis_option['select_value']}
    #     print(f"Selecting subset with: {sel_dict}")
    #     sub_set = avg_sub.isel(**sel_dict).squeeze()
    #     print("subset dimensions", list(sub_set.dims))
    #     return sub_set

    def generate_subset_for_result(
            self, result_name: str, has_new_data: bool = False) -> xr.DataArray:
        """
        Generate a subset DataArray for a single result variable.

        Applies only the averaging and index-selection steps that are relevant
        to this result's own dimensions.  Dimensions assigned the x-axis or
        y-axis role are left intact so the caller can plot them.

        The averaged base dataset is cached via ``_get_averaged_subset``, so
        calling this method for multiple results within a single render cycle
        only triggers re-averaging once (on the first call with has_new_data=True).

        Args:
            result_name: Name of the result variable in full_data_set.
            has_new_data: Forwarded to _get_averaged_subset; set True only on
                the first result in a render cycle to avoid redundant work.
        Returns:
            xr.DataArray for the result, with select_value dims collapsed.
        """
        avg_sub = self._get_averaged_subset(has_new_data=has_new_data)
        da = avg_sub[result_name]
        result_dims = set(da.dims)
        # Never isel a dim that is assigned as this result's x or y axis.
        axes = self.result_axes[result_name]
        protected = {ax.name for ax in (axes['x-axis'] + axes['y-axis']) if ax is not None}
        sel_dict = {
            d.name: d.select_index
            for d in axes['select_value']
            if d.name in result_dims and d.name not in protected
        }
        if sel_dict:
            da = da.isel(**sel_dict)
        return da.squeeze()

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
        for result, axes in self.result_axes.items():
            for dim in axes['select_value']:
                print(f"Updating slider for {result}/{dim.name}")
                dim.slider._props["max"] = len(self.full_data_set[dim.name]) - 1
                dim.slider.update()
