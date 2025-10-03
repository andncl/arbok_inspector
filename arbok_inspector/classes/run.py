"""
Run class representing a single run of the experiment.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

import json
from qcodes.dataset import load_by_id
from nicegui import ui

from arbok_inspector.classes.dim import Dim
from arbok_inspector.widgets.build_xarray_grid import build_xarray_grid

if TYPE_CHECKING:
    from qcodes.dataset.data_set import DataSet
    from xarray import Dataset
AXIS_OPTIONS = ['average', 'select_value', 'y-axis', 'x-axis']

class Run:
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
        self.dataset: DataSet = load_by_id(run_id)
        self.full_data_set: Dataset = self.dataset.to_xarray_dataset()

        self.together_sweeps: bool = False
        self.parallel_sweep_axes: dict = {}
        self.sweep_dict: dict[int, Dim] = {}
        self.load_sweep_dict()
        self.dims: list[Dim] = list(self.sweep_dict.values())
        self.dim_axis_option: dict[str, str|list[Dim]] = self.set_dim_axis_option()
        print(self.dims)

        self.plot_selection: list[str] = []
        self.plots_per_column: int = 2

    def load_sweep_dict(self):
        """
        Load the sweep dictionary from the dataset
        TODO: check metadata for sweep information!
        Returns:
            sweep_dict (dict): Dictionary with sweep information
            is_together (bool): True if all sweeps are together, False otherwise
        """
        if "parallel_sweep_axes" in self.dataset.metadata:
            conf = self.dataset.metadata["parallel_sweep_axes"]
            conf = conf.replace("'", '"')  # Ensure JSON compatibility
            print( conf)
            conf = json.loads(conf)
            self.parallel_sweep_axes = {int(i): sweeps for i, sweeps in conf.items()}
            self.together_sweeps = True
        else:
            dims = self.full_data_set.dims
            self.parallel_sweep_axes = {i: [dim] for i, dim in enumerate(dims)}
            self.together_sweeps = False
        self.sweep_dict = {
            i: Dim(names[0]) for i, names in self.parallel_sweep_axes.items()
            }
        print(self.sweep_dict)
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
        for dim in self.dims:
            if 'iteration' in dim.name:
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

    def update_subset_dims(self, dim: Dim, selection: str, index = None):
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
            if old_dim is not None:
                # Set previous dim (having this option) to 'select_value'
                # Required since x and y axis ahve to be unique
                print(f"Updating {old_dim.name} to {dim.name} on {selection}")
                if old_dim.option in ['x-axis', 'y-axis']:
                    self.dim_axis_option['select_value'].append(old_dim)
                    old_dim.option = 'select_value'
                    old_dim.ui_selector.value = 'select_value'
                    self.update_subset_dims(old_dim, 'select_value', old_dim.select_index)
        dim.ui_selector.update()

    def generate_subset(self):
        """
        Generate the subset of the full dataset based on the current dimension options.
        Returns:
            sub_set (xarray.Dataset): The subset of the full dataset
        """
        # TODO: take the averaging out of this! We only want to average if necessary
        # averaging can be computationally intensive!
        sub_set = self.full_data_set
        for avg_axis in self.dim_axis_option['average']:
            sub_set = sub_set.mean(dim=avg_axis.name)
        sel_dict = {d.name: d.select_index for d in self.dim_axis_option['select_value']}
        sub_set = sub_set.isel(**sel_dict).squeeze()
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
        build_xarray_grid(self)
