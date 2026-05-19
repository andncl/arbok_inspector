"""
Run class representing a single run of the experiment.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Callable

from abc import ABC, abstractmethod
import ast

from arbok_inspector.classes.dim import Dim
from arbok_inspector.analysis.prepare_data import bin_over_axis, compute_fft

from xarray import Dataset, DataArray

if TYPE_CHECKING:
    from arbok_inspector.state import ArbokInspector


class BaseRun(ABC):
    """
    Class representing a run with its data and methods.
    Pure data/logic layer — no UI imports.
    """
    full_data_set: Dataset
    name: str

    def __init__(self, run_id: int, inspector: ArbokInspector):
        self.run_id: int = run_id
        self.title: str = f'Run ID: {run_id}  (-> add experiment)'
        self.inspector: ArbokInspector = inspector
        self.parallel_sweep_axes: dict[int, list[str]] = {}
        self.sweep_dict: dict[int, Dim] = {}
        self._database_columns: dict[str, dict[str, str]] = {}
        self.dims: list[Dim] = []
        self.plot_selection: list[str] = []
        self.show_histogram: bool = False
        self.fft_freq_range: dict[str, int] | None = None
        self.fft_representation: str = 'PSD'
        self.plots_per_column: int = 2

        self._cached_avg: dict[str, DataArray] | None = None
        self._cached_avg_dims: set[str] | None = None

        self._on_dim_changed: Callable[[Dim], None] | None = None
        self._on_sliders_need_update: Callable[[], None] | None = None

    @property
    def show_fft(self) -> bool:
        """True when any dimension is assigned to the 'fft' role."""
        return self.dim_axis_option.get('fft') is not None

    def set_on_dim_changed(self, callback: Callable[[Dim], None]):
        """Register callback invoked when a dim's option changes programmatically."""
        self._on_dim_changed = callback

    def set_on_sliders_need_update(self, callback: Callable[[], None]):
        """Register callback invoked when slider max values need refreshing."""
        self._on_sliders_need_update = callback

    @property
    def database_columns(self) -> dict[str, dict[str, str]]:
        return self._database_columns

    @abstractmethod
    def _get_database_columns(self) -> dict[str, dict[str, str]]:
        pass

    @abstractmethod
    def _load_dataset(self) -> Dataset:
        pass

    @abstractmethod
    def get_qua_code(self, as_string: bool = False) -> str:
        pass

    def prepare_run(self, avg_axis: str | None = None, result_keywords: str = "") -> None:
        """Prepare the run by loading the dataset."""
        self._database_columns = self._get_database_columns()
        self.full_data_set: Dataset = self._load_dataset()
        self.process_run_data(avg_axis=avg_axis, result_keywords=result_keywords)

    def process_run_data(self, avg_axis: str | None = None, result_keywords: str = "") -> None:
        """Initialize dimension structure and plot selection from loaded dataset."""
        self._invalidate_cache()
        self.load_sweep_dict()
        self.dims = list(self.sweep_dict.values())
        self.dim_axis_option = self.set_dim_axis_option(avg_axis=avg_axis)
        self.plot_selection = self.select_results_by_keywords(result_keywords)

    def _invalidate_cache(self):
        """Clear the averaged data cache."""
        self._cached_avg = None
        self._cached_avg_dims = None

    def load_sweep_dict(self) -> dict[int, Dim]:
        """Build sweep_dict mapping dimension index to Dim objects."""
        self.parallel_sweep_axes = {}
        for i, dim in enumerate(self.full_data_set.dims):
            self.parallel_sweep_axes[i] = [
                name for name, coord in self.full_data_set.coords.items()
                if dim in coord.dims
            ]
        self.sweep_dict = {
            i: Dim(names[0]) for i, names in self.parallel_sweep_axes.items()
        }
        return self.sweep_dict

    def set_dim_axis_option(self, avg_axis: str | None = None):
        """
        Assign default roles to dimensions:
        1. Dims matching avg_axis → 'average'
        2. Innermost remaining → 'x-axis'
        3. Next innermost remaining → 'y-axis'
        4. All others → 'select_value'
        """
        averaged = []
        remaining = []
        for dim in self.dims:
            if avg_axis and avg_axis in dim.name:
                dim.option = 'average'
                averaged.append(dim)
            else:
                remaining.append(dim)

        x_dim = remaining.pop() if remaining else None
        if x_dim:
            x_dim.option = 'x-axis'

        y_dim = remaining.pop() if remaining else None
        if y_dim:
            y_dim.option = 'y-axis'

        for dim in remaining:
            dim.option = 'select_value'
            dim.select_index = 0

        return {
            'average': averaged,
            'x-axis': x_dim,
            'y-axis': y_dim,
            'select_value': remaining,
            'fft': None,
        }

    def select_results_by_keywords(self, keywords: str) -> list[str]:
        """
        Select results whose names match the given keywords.

        Args:
            keywords: String repr of a Python list. Each element can be a string
                      (substring match) or tuple of strings (all must match).
        Returns:
            List of matching data variable names. Falls back to [first_var] if
            nothing matches or keywords are invalid.
        """
        parsed = self._parse_keywords(keywords)
        selected = set()
        for result in self.full_data_set.data_vars:
            result_str = str(result)
            for kw in parsed:
                if isinstance(kw, str) and kw in result_str:
                    selected.add(result)
                elif isinstance(kw, tuple) and all(s in result_str for s in kw):
                    selected.add(result)
        if not selected:
            return [next(iter(self.full_data_set.data_vars))]
        return list(selected)

    @staticmethod
    def _parse_keywords(keywords: str) -> list:
        """Parse a keyword string into a list of str/tuple matchers."""
        if not keywords:
            return []
        try:
            parsed = ast.literal_eval(keywords)
        except (SyntaxError, ValueError):
            return []
        if not isinstance(parsed, list):
            parsed = [parsed]
        return parsed

    def update_subset_dims(self, dim: Dim, selection: str, index: int = 0):
        """
        Move a dimension to a new role. Handles fallback: setting x-axis, y-axis,
        or fft demotes the previous holder to select_value.
        """
        self._remove_dim_from_current_role(dim)

        if selection in ('average', 'select_value'):
            dim.option = selection
            dim.select_index = index
            self.dim_axis_option[selection].append(dim)
            self._notify_dim_changed(dim)
            return

        if selection in ('x-axis', 'y-axis', 'fft'):
            old_dim = self.dim_axis_option.get(selection)
            self.dim_axis_option[selection] = dim
            dim.option = selection
            self._notify_dim_changed(dim)
            if old_dim and old_dim is not dim:
                self._demote_to_select_value(old_dim)

    def _remove_dim_from_current_role(self, dim: Dim):
        """Remove dim from whatever role it currently occupies."""
        if dim.option == 'average':
            self.dim_axis_option['average'].remove(dim)
        elif dim.option == 'select_value':
            self.dim_axis_option['select_value'].remove(dim)
            dim.select_index = 0
        elif dim.option in ('x-axis', 'y-axis', 'fft'):
            self.dim_axis_option[dim.option] = None
        dim.option = None

    def _demote_to_select_value(self, dim: Dim):
        """Demote a dim from x/y-axis to select_value."""
        dim.option = 'select_value'
        self.dim_axis_option['select_value'].append(dim)
        self._notify_dim_changed(dim)

    def _notify_dim_changed(self, dim: Dim):
        if self._on_dim_changed:
            self._on_dim_changed(dim)

    def update_plot_selection(self, selected: bool, readout_name: str) -> bool:
        """
        Add or remove a result from the plot selection.

        Args:
            selected: True to add, False to remove.
            readout_name: Name of the data variable.
        Returns:
            True if the selection was actually modified.
        """
        if selected and readout_name not in self.plot_selection:
            self.plot_selection.append(readout_name)
            return True
        elif not selected and readout_name in self.plot_selection:
            self.plot_selection.remove(readout_name)
            return True
        return False

    # ─── Subsetting / Averaging ───────────────────────────────────────────

    def _expected_plot_dims(self, include_current: bool = False, include_fft: bool = False) -> set[str]:
        """Compute the set of dimension names that should remain after averaging."""
        dims = {d.name for d in self.dim_axis_option['select_value']}
        if self.dim_axis_option.get('x-axis'):
            dims.add(self.dim_axis_option['x-axis'].name)
        if self.dim_axis_option.get('y-axis'):
            dims.add(self.dim_axis_option['y-axis'].name)
        if self.dim_axis_option.get('fft'):
            dims.add(self.dim_axis_option['fft'].name)
        if include_current:
            dims.add('Current')
        if include_fft:
            dims.add('frequency')
        return dims

    def _get_averaged_dict(self, has_new_data: bool = False) -> dict[str, DataArray]:
        """
        Get (or compute) the averaged data as a dict of DataArrays.
        Uses cache when the averaging dimensions haven't changed.
        """
        expected = self._expected_plot_dims()
        if (not has_new_data
                and self._cached_avg is not None
                and self._cached_avg_dims == expected):
            return self._cached_avg

        avg_names = [d.name for d in self.dim_axis_option['average']]
        averaged = self.full_data_set.mean(dim=avg_names)
        result = {name: var for name, var in averaged.data_vars.items()}
        self._cached_avg = result
        self._cached_avg_dims = expected
        self._on_sliders_updated()
        return result

    def _get_binned_dict(self, has_new_data: bool = False, bins: int | list = 51) -> dict[str, DataArray]:
        """
        Get (or compute) binned data for histogram mode.
        """
        expected = self._expected_plot_dims(include_current=True)
        if (not has_new_data
                and self._cached_avg is not None
                and self._cached_avg_dims == expected):
            return self._cached_avg

        avg_names = [d.name for d in self.dim_axis_option['average']]
        binned = {}
        for var_name, var in self.full_data_set.data_vars.items():
            binned[var_name] = bin_over_axis(var, dim=avg_names, bins=bins)
        self._cached_avg = binned
        self._cached_avg_dims = expected
        self._on_sliders_updated()
        return binned

    def _apply_selection(self, data: dict[str, DataArray]) -> dict[str, DataArray]:
        """Apply isel for all select_value dims, then squeeze."""
        sel_dict = {d.name: d.select_index for d in self.dim_axis_option['select_value']}
        if not sel_dict:
            return data
        return {name: var.isel(**sel_dict).squeeze() for name, var in data.items()}

    def _on_sliders_updated(self):
        if self._on_sliders_need_update:
            self._on_sliders_need_update()

    def generate_subset_dict(self, has_new_data: bool = False) -> dict[str, DataArray]:
        """Generate the plotable subset as a dict of DataArrays."""
        averaged = self._get_averaged_dict(has_new_data)
        return self._apply_selection(averaged)

    def generate_binned_subset(self, has_new_data: bool = False, bins: int | list = 51) -> dict[str, DataArray]:
        """Generate binned subset (histogram mode)."""
        binned = self._get_binned_dict(has_new_data, bins)
        return self._apply_selection(binned)

    def generate_subset(self, has_new_data: bool = False) -> Dataset:
        """Generate the plotable subset as an xarray Dataset."""
        subset_dict = self.generate_subset_dict(has_new_data)
        return Dataset(subset_dict)

    def generate_fft_subset(
        self, has_new_data: bool = False
    ) -> dict[str, DataArray]:
        """
        Generate FFT power spectrum subset.
        Pipeline: average → FFT along fft dim → slice freq range → isel for select_value dims.

        Args:
            has_new_data: Force recomputation of averaged data
        Returns:
            Dict of DataArrays with 'frequency' replacing the FFT dim
        Raises:
            ValueError: If no dimension is assigned to 'fft' role
        """
        fft_dim = self.dim_axis_option.get('fft')
        if fft_dim is None:
            raise ValueError("No dimension assigned to 'fft' role")

        averaged = self._get_averaged_dict(has_new_data)
        fft_result = {}
        for name, var in averaged.items():
            if fft_dim.name in var.dims:
                fft_result[name] = compute_fft(var, dim=fft_dim.name, representation=self.fft_representation)
            else:
                fft_result[name] = var

        if self.fft_freq_range is not None:
            freq_dim = next(
                (d for d in next(iter(fft_result.values())).dims
                 if d.endswith('frequency')), None)
            if freq_dim:
                lo = self.fft_freq_range['min']
                hi = self.fft_freq_range['max']
                fft_result = {
                    name: arr.isel({freq_dim: slice(lo, hi + 1)})
                    for name, arr in fft_result.items()
                    if freq_dim in arr.dims
                } | {
                    name: arr for name, arr in fft_result.items()
                    if freq_dim not in arr.dims
                }

        return self._apply_selection(fft_result)
