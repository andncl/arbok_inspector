"""
Run class representing a single run of the experiment.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Iterable

from abc import ABC, abstractmethod
import ast

from arbok_inspector.classes.dim import Dim
from arbok_inspector.classes.view_state import ViewState
from arbok_inspector.analysis.prepare_data import (
    bin_over_axis, compute_decay_spectrum, compute_fft)

from xarray import Dataset, DataArray

if TYPE_CHECKING:
    from arbok_inspector.state import ArbokInspector


SINGLE_DIM_ROLES = ('x-axis', 'y-axis', 'fft', 'decay')
"""Roles held by at most one dim; assigning one demotes the previous holder."""


class BaseRun(ABC):
    """
    Class representing a run with its data and methods.
    Pure data/logic layer — no UI imports.

    Thread safety: `compute_subset` and `reload_dataset` run in a worker
    thread. They only read the immutable `ViewState` they are given (never the
    mutable dims), and the caller guarantees one computation per run at a time.
    """
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
        self.decay_range: dict[str, int] | None = None
        self.plots_per_column: int = 2
        self.last_subset: dict[str, DataArray] | None = None

        self._data_version: int = 0
        self._caches: dict[str, tuple[tuple, dict[str, DataArray]]] = {}

        self._on_dim_changed: Callable[[Dim], None] | None = None

    @property
    def show_fft(self) -> bool:
        """True when any dimension is assigned to the 'fft' role."""
        return self.dim_axis_option.get('fft') is not None

    @property
    def show_decay(self) -> bool:
        """True when any dimension is assigned to the 'decay' role."""
        return self.dim_axis_option.get('decay') is not None

    def set_on_dim_changed(self, callback: Callable[[Dim], None]):
        """Register callback invoked when a dim's option changes programmatically."""
        self._on_dim_changed = callback

    @property
    def database_columns(self) -> dict[str, dict[str, str]]:
        return self._database_columns

    @property
    def full_data_set(self) -> Dataset:
        """The complete dataset of the run."""
        return self._full_data_set

    @full_data_set.setter
    def full_data_set(self, dataset: Dataset) -> None:
        """Replacing the dataset bumps the data version, invalidating all caches."""
        self._full_data_set = dataset
        self._data_version += 1

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
        self.full_data_set = self._load_dataset()
        self.process_run_data(avg_axis=avg_axis, result_keywords=result_keywords)

    def reload_dataset(self) -> None:
        """Reload the dataset from the database, keeping all dim roles."""
        self.full_data_set = self._load_dataset()

    def process_run_data(self, avg_axis: str | None = None, result_keywords: str = "") -> None:
        """Initialize dimension structure and plot selection from loaded dataset."""
        self._invalidate_cache()
        self.load_sweep_dict()
        self.dims = list(self.sweep_dict.values())
        self.dim_axis_option = self.set_dim_axis_option(avg_axis=avg_axis)
        self.plot_selection = self.select_results_by_keywords(result_keywords)

    def _invalidate_cache(self):
        """Clear all cached averaged, binned and FFT data."""
        self._caches = {}

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
            'decay': None,
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
        fft or decay demotes the previous holder to select_value.
        """
        self._remove_dim_from_current_role(dim)

        if selection in ('average', 'select_value'):
            dim.option = selection
            dim.select_index = index
            self.dim_axis_option[selection].append(dim)
            self._notify_dim_changed(dim)
            return

        if selection in SINGLE_DIM_ROLES:
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
        elif dim.option in SINGLE_DIM_ROLES:
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

    def snapshot_view(self) -> ViewState:
        """Capture the current dim roles and plot options as an immutable ViewState."""
        options = self.dim_axis_option

        def dim_name(role: str) -> str | None:
            dim = options.get(role)
            return dim.name if dim is not None else None

        freq_range = self.fft_freq_range
        decay_range = self.decay_range
        return ViewState(
            avg_dims=tuple(d.name for d in options['average']),
            x_dim=dim_name('x-axis'),
            y_dim=dim_name('y-axis'),
            fft_dim=dim_name('fft'),
            selection=tuple((d.name, d.select_index) for d in options['select_value']),
            plot_selection=tuple(self.plot_selection),
            show_histogram=self.show_histogram,
            fft_representation=self.fft_representation,
            fft_freq_range=(
                (int(freq_range['min']), int(freq_range['max']))
                if freq_range is not None else None),
            decay_dim=dim_name('decay'),
            decay_range=(
                (int(decay_range['min']), int(decay_range['max']))
                if decay_range is not None else None),
        )

    def compute_subset(
        self,
        view: ViewState,
        has_new_data: bool = False,
        variables: Iterable[str] | None = None,
    ) -> dict[str, DataArray]:
        """
        Compute the plotable data for the given view. Only the selected
        variables are processed. Safe to run in a worker thread.

        Args:
            view: Snapshot of the plot settings (see `snapshot_view`)
            has_new_data: Force recomputation, bypassing all caches
            variables: Variables to compute, defaults to `view.plot_selection`
        Returns:
            Dict of DataArrays with all select_value dims applied
        """
        if variables is None:
            variables = view.plot_selection
        names = [n for n in variables if n in self.full_data_set.data_vars]
        if view.fft_dim is not None:
            data = self._fft_data(view, names, has_new_data)
        elif view.decay_dim is not None:
            data = self._decay_data(view, names, has_new_data)
        elif view.show_histogram:
            data = self._binned_data(view, names, has_new_data)
        else:
            data = self._averaged_data(view, names, has_new_data)
        subset = self._apply_selection(data, view.selection)
        self.last_subset = subset
        return subset

    def _resolve_dim(self, name: str) -> str:
        """Map a (possibly parallel) coordinate name to the dimension it spans."""
        if name in self.full_data_set.dims:
            return name
        coord = self.full_data_set.coords.get(name)
        if coord is not None and coord.ndim == 1:
            return coord.dims[0]
        return name

    def _cache_for(self, kind: str, key: tuple, force: bool) -> dict[str, DataArray]:
        """Return the per-variable cache of `kind`, emptied if its key changed."""
        cached_key, entries = self._caches.get(kind, (None, None))
        if force or entries is None or cached_key != key:
            entries = {}
            self._caches[kind] = (key, entries)
        return entries

    def _averaged_data(
        self, view: ViewState, names: list[str], force: bool = False
    ) -> dict[str, DataArray]:
        """Mean over the average dims, cached per variable."""
        avg_dims = tuple(self._resolve_dim(d) for d in view.avg_dims)
        cache = self._cache_for('avg', (self._data_version, avg_dims), force)
        for name in names:
            if name not in cache:
                var = self.full_data_set[name]
                dims = [d for d in avg_dims if d in var.dims]
                cache[name] = var.mean(dim=dims) if dims else var
        return {name: cache[name] for name in names}

    def _binned_data(
        self, view: ViewState, names: list[str], force: bool = False,
        bins: int | list = 51,
    ) -> dict[str, DataArray]:
        """Histogram over the average dims (histogram mode), cached per variable."""
        avg_dims = tuple(self._resolve_dim(d) for d in view.avg_dims)
        bins_key = bins if isinstance(bins, int) else tuple(bins)
        cache = self._cache_for(
            'binned', (self._data_version, avg_dims, bins_key), force)
        for name in names:
            if name not in cache:
                cache[name] = bin_over_axis(
                    self.full_data_set[name], dim=list(avg_dims), bins=bins)
        return {name: cache[name] for name in names}

    def _fft_data(
        self, view: ViewState, names: list[str], force: bool = False
    ) -> dict[str, DataArray]:
        """
        Average → FFT along the fft dim (cached) → slice the frequency range.
        Changing only the frequency range therefore never recomputes the FFT.
        """
        if view.fft_dim is None:
            raise ValueError("No dimension assigned to 'fft' role")
        fft_dim = self._resolve_dim(view.fft_dim)
        averaged = self._averaged_data(view, names, force)
        avg_dims = tuple(self._resolve_dim(d) for d in view.avg_dims)
        cache = self._cache_for(
            'fft',
            (self._data_version, avg_dims, fft_dim, view.fft_representation),
            force)
        result = {}
        for name in names:
            var = averaged[name]
            if fft_dim not in var.dims:
                result[name] = var
                continue
            if name not in cache:
                cache[name] = compute_fft(
                    var, dim=fft_dim, representation=view.fft_representation)
            arr = cache[name]
            if view.fft_freq_range is not None:
                lo, hi = view.fft_freq_range
                freq_dim = arr.dims[var.get_axis_num(fft_dim)]
                arr = arr.isel({freq_dim: slice(lo, hi + 1)})
            result[name] = arr
        return result

    def _decay_data(
        self, view: ViewState, names: list[str], force: bool = False
    ) -> dict[str, DataArray]:
        """
        Average → decay-time spectrum along the decay dim (cached) → slice the
        decay-time range. Changing only the range never recomputes the spectrum.
        """
        if view.decay_dim is None:
            raise ValueError("No dimension assigned to 'decay' role")
        decay_dim = self._resolve_dim(view.decay_dim)
        averaged = self._averaged_data(view, names, force)
        avg_dims = tuple(self._resolve_dim(d) for d in view.avg_dims)
        cache = self._cache_for(
            'decay', (self._data_version, avg_dims, decay_dim), force)
        result = {}
        for name in names:
            var = averaged[name]
            if decay_dim not in var.dims:
                result[name] = var
                continue
            if name not in cache:
                cache[name] = compute_decay_spectrum(var, dim=decay_dim)
            arr = cache[name]
            if view.decay_range is not None:
                lo, hi = view.decay_range
                spectrum_dim = arr.dims[var.get_axis_num(decay_dim)]
                arr = arr.isel({spectrum_dim: slice(lo, hi + 1)})
            result[name] = arr
        return result

    def _apply_selection(
        self, data: dict[str, DataArray],
        selection: tuple[tuple[str, int], ...] | None = None,
    ) -> dict[str, DataArray]:
        """Apply isel for all select_value dims, then squeeze."""
        if selection is None:
            selection = self.snapshot_view().selection
        if not selection:
            return data
        indices = {self._resolve_dim(name): index for name, index in selection}
        selected = {}
        for name, var in data.items():
            var_indices = {
                d: min(i, var.sizes[d] - 1)
                for d, i in indices.items() if d in var.dims}
            selected[name] = var.isel(var_indices).squeeze()
        return selected

    def _all_variables(self) -> list[str]:
        return list(self.full_data_set.data_vars)

    def generate_subset_dict(self, has_new_data: bool = False) -> dict[str, DataArray]:
        """Generate the averaged subset of all variables as a dict of DataArrays."""
        view = self.snapshot_view()
        averaged = self._averaged_data(view, self._all_variables(), has_new_data)
        return self._apply_selection(averaged, view.selection)

    def generate_binned_subset(self, has_new_data: bool = False, bins: int | list = 51) -> dict[str, DataArray]:
        """Generate binned subset of all variables (histogram mode)."""
        view = self.snapshot_view()
        binned = self._binned_data(view, self._all_variables(), has_new_data, bins)
        return self._apply_selection(binned, view.selection)

    def generate_subset(self, has_new_data: bool = False) -> Dataset:
        """Generate the plotable subset as an xarray Dataset."""
        subset_dict = self.generate_subset_dict(has_new_data)
        return Dataset(subset_dict)

    def generate_fft_subset(
        self, has_new_data: bool = False
    ) -> dict[str, DataArray]:
        """
        Generate FFT power spectrum subset of all variables.
        Pipeline: average → FFT along fft dim → slice freq range → isel for select_value dims.

        Args:
            has_new_data: Force recomputation of averaged data
        Returns:
            Dict of DataArrays with 'frequency' replacing the FFT dim
        Raises:
            ValueError: If no dimension is assigned to 'fft' role
        """
        view = self.snapshot_view()
        fft_result = self._fft_data(view, self._all_variables(), has_new_data)
        return self._apply_selection(fft_result, view.selection)

    def generate_decay_subset(self, has_new_data: bool = False) -> dict[str, DataArray]:
        """
        Generate the decay-time spectrum subset of all variables.
        Pipeline: average → decay spectrum along decay dim → slice range → isel.

        Raises:
            ValueError: If no dimension is assigned to 'decay' role
        """
        view = self.snapshot_view()
        decay_result = self._decay_data(view, self._all_variables(), has_new_data)
        return self._apply_selection(decay_result, view.selection)
