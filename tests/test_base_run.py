"""Tests for BaseRun dimension assignment, selection fallbacks, and subsetting."""
import numpy as np
import pytest

from arbok_inspector.classes.dim import Dim
from tests.conftest import ConcreteRun, make_dataset_3d, make_dataset_2d, make_dataset_4d


class TestDimAxisOptionDefaults:
    """Test set_dim_axis_option: initial assignment of dimension roles."""

    def test_3d_with_iteration_avg(self, run_3d):
        """iteration→average, frequency→x-axis, voltage→y-axis."""
        opts = run_3d.dim_axis_option
        avg_names = [d.name for d in opts['average']]
        assert "iteration" in avg_names
        assert opts['x-axis'].name == "frequency"
        assert opts['y-axis'].name == "voltage"
        assert opts['select_value'] == []

    def test_2d_no_avg(self, run_2d):
        """No avg keyword → frequency→x-axis, voltage→y-axis."""
        opts = run_2d.dim_axis_option
        assert opts['average'] == []
        assert opts['x-axis'].name == "frequency"
        assert opts['y-axis'].name == "voltage"
        assert opts['select_value'] == []

    def test_1d_no_avg(self, run_1d):
        """Single dim → frequency→x-axis, no y-axis."""
        opts = run_1d.dim_axis_option
        assert opts['x-axis'].name == "frequency"
        assert opts['y-axis'] is None
        assert opts['average'] == []
        assert opts['select_value'] == []

    def test_4d_with_iteration_avg(self, run_4d):
        """iteration→average, frequency→x-axis, voltage→y-axis, rep→select_value."""
        opts = run_4d.dim_axis_option
        avg_names = [d.name for d in opts['average']]
        assert "iteration" in avg_names
        assert opts['x-axis'].name == "frequency"
        assert opts['y-axis'].name == "voltage"
        sel_names = [d.name for d in opts['select_value']]
        assert "rep" in sel_names

    def test_4d_select_value_index_is_zero(self, run_4d):
        """Dims assigned to select_value should default to index 0."""
        for dim in run_4d.dim_axis_option['select_value']:
            assert dim.select_index == 0

    def test_avg_axis_none_means_no_averaging(self):
        """If avg_axis is None, no dims are set to average."""
        ds = make_dataset_3d()
        run = ConcreteRun(ds)
        run.prepare_run(avg_axis=None, result_keywords="")
        avg_names = [d.name for d in run.dim_axis_option['average']]
        assert avg_names == []


class TestUpdateSubsetDims:
    """Test update_subset_dims: role changes and fallback/overwrite logic."""

    def test_move_dim_to_average(self, run_3d):
        """Moving voltage from y-axis to average."""
        voltage_dim = run_3d.dim_axis_option['y-axis']
        assert voltage_dim.name == "voltage"
        run_3d.update_subset_dims(voltage_dim, 'average')
        assert voltage_dim.option == "average"
        assert voltage_dim in run_3d.dim_axis_option['average']

    def test_move_dim_to_select_value(self, run_3d):
        """Moving voltage from y-axis to select_value."""
        voltage_dim = run_3d.dim_axis_option['y-axis']
        run_3d.update_subset_dims(voltage_dim, 'select_value', index=2)
        assert voltage_dim.option == "select_value"
        assert voltage_dim.select_index == 2
        assert voltage_dim in run_3d.dim_axis_option['select_value']

    def test_x_axis_overwrite_demotes_old_dim(self, run_4d):
        """Setting a new dim as x-axis demotes the old x-axis to select_value."""
        old_x = run_4d.dim_axis_option['x-axis']
        assert old_x.name == "frequency"
        # Move voltage to x-axis (it's currently y-axis)
        voltage_dim = run_4d.dim_axis_option['y-axis']
        run_4d.update_subset_dims(voltage_dim, 'x-axis')
        assert run_4d.dim_axis_option['x-axis'] is voltage_dim
        assert voltage_dim.option == "x-axis"
        # Old x-axis should now be select_value
        assert old_x.option == "select_value"
        assert old_x in run_4d.dim_axis_option['select_value']

    def test_y_axis_overwrite_demotes_old_dim(self, run_4d):
        """Setting a new dim as y-axis demotes the old y-axis to select_value."""
        old_y = run_4d.dim_axis_option['y-axis']
        assert old_y.name == "voltage"
        # Move rep (currently select_value) to y-axis
        rep_dim = run_4d.dim_axis_option['select_value'][0]
        assert rep_dim.name == "rep"
        run_4d.update_subset_dims(rep_dim, 'y-axis')
        assert run_4d.dim_axis_option['y-axis'] is rep_dim
        assert rep_dim.option == "y-axis"
        # Old y-axis should be demoted to select_value
        assert old_y.option == "select_value"
        assert old_y in run_4d.dim_axis_option['select_value']

    def test_move_from_average_to_x_axis(self, run_3d):
        """Moving iteration from average to x-axis displaces old x-axis."""
        iteration_dim = run_3d.dim_axis_option['average'][0]
        old_x = run_3d.dim_axis_option['x-axis']
        run_3d.update_subset_dims(iteration_dim, 'x-axis')
        assert iteration_dim.option == "x-axis"
        assert run_3d.dim_axis_option['x-axis'] is iteration_dim
        assert iteration_dim not in run_3d.dim_axis_option['average']
        # Old x-axis demoted
        assert old_x.option == "select_value"

    def test_move_from_select_value_to_average(self, run_4d):
        """Moving rep from select_value to average."""
        rep_dim = run_4d.dim_axis_option['select_value'][0]
        run_4d.update_subset_dims(rep_dim, 'average')
        assert rep_dim.option == "average"
        assert rep_dim in run_4d.dim_axis_option['average']
        assert rep_dim not in run_4d.dim_axis_option['select_value']

    def test_callback_fires_on_dim_change(self, run_3d):
        """The on_dim_changed callback fires when a dim option is changed."""
        changed_dims = []
        run_3d.set_on_dim_changed(lambda dim: changed_dims.append(dim))
        voltage_dim = run_3d.dim_axis_option['y-axis']
        run_3d.update_subset_dims(voltage_dim, 'average')
        assert voltage_dim in changed_dims

    def test_callback_fires_for_demoted_dim(self, run_4d):
        """When overwriting x-axis, callback fires for both new and demoted dim."""
        changed_dims = []
        run_4d.set_on_dim_changed(lambda dim: changed_dims.append(dim))
        voltage_dim = run_4d.dim_axis_option['y-axis']
        old_x = run_4d.dim_axis_option['x-axis']
        run_4d.update_subset_dims(voltage_dim, 'x-axis')
        assert old_x in changed_dims
        assert voltage_dim in changed_dims


class TestSelectResultsByKeywords:
    """Test keyword-based result selection."""

    def test_empty_keywords_selects_first(self, run_3d):
        """Empty keywords string → selects first data var."""
        results = run_3d.select_results_by_keywords("")
        assert len(results) == 1
        assert results[0] in run_3d.full_data_set.data_vars

    def test_string_keyword_match(self, run_3d):
        """A string keyword matches results containing it."""
        results = run_3d.select_results_by_keywords("['readout__I']")
        assert "readout__I" in results
        assert "readout__Q" not in results

    def test_tuple_keyword_all_parts_must_match(self, run_3d):
        """A tuple keyword requires all substrings to be present."""
        results = run_3d.select_results_by_keywords("[('readout', 'Q')]")
        assert "readout__Q" in results
        assert "readout__I" not in results

    def test_no_match_falls_back_to_first(self, run_3d):
        """If no keyword matches, fall back to first data var."""
        results = run_3d.select_results_by_keywords("['nonexistent']")
        assert len(results) == 1
        assert results[0] in run_3d.full_data_set.data_vars

    def test_invalid_keywords_returns_first(self, run_3d):
        """Invalid Python literal falls back gracefully."""
        results = run_3d.select_results_by_keywords("not a list [[[")
        assert len(results) == 1

    def test_multiple_keywords(self, run_3d):
        """Multiple keywords can select multiple results."""
        results = run_3d.select_results_by_keywords("['readout__I', 'readout__Q']")
        assert "readout__I" in results
        assert "readout__Q" in results


class TestUpdatePlotSelection:
    """Test plot selection toggling."""

    def test_add_to_selection(self, run_3d):
        """Adding a new result returns True."""
        run_3d.plot_selection = []
        changed = run_3d.update_plot_selection(True, "readout__I")
        assert changed is True
        assert "readout__I" in run_3d.plot_selection

    def test_remove_from_selection(self, run_3d):
        """Removing an existing result returns True."""
        run_3d.plot_selection = ["readout__I", "readout__Q"]
        changed = run_3d.update_plot_selection(False, "readout__I")
        assert changed is True
        assert "readout__I" not in run_3d.plot_selection

    def test_no_duplicates(self, run_3d):
        """Adding a result that's already present is a no-op (no duplicates)."""
        run_3d.plot_selection = ["readout__I"]
        changed = run_3d.update_plot_selection(True, "readout__I")
        assert changed is False
        assert run_3d.plot_selection == ["readout__I"]

    def test_remove_nonexistent_is_noop(self, run_3d):
        """Removing a result that's not selected returns False."""
        run_3d.plot_selection = ["readout__Q"]
        changed = run_3d.update_plot_selection(False, "readout__I")
        assert changed is False
        assert run_3d.plot_selection == ["readout__Q"]


class TestGenerateSubset:
    """Test data subsetting logic."""

    def test_generate_subset_dict_3d(self, run_3d):
        """3D run averaged over iteration → 2D results (voltage x frequency)."""
        subset = run_3d.generate_subset_dict(has_new_data=True)
        assert "readout__I" in subset
        assert "readout__Q" in subset
        # After averaging iteration, we should have voltage x frequency
        dims = list(subset["readout__I"].dims)
        assert "voltage" in dims
        assert "frequency" in dims
        assert "iteration" not in dims

    def test_generate_subset_dict_with_select(self, run_4d):
        """4D run: iteration avg, rep select → voltage x frequency result."""
        subset = run_4d.generate_subset_dict(has_new_data=True)
        assert "result_A" in subset
        dims = list(subset["result_A"].dims)
        assert "iteration" not in dims
        assert "rep" not in dims
        assert "voltage" in dims
        assert "frequency" in dims

    def test_generate_subset_caching(self, run_3d):
        """Calling generate_subset_dict twice reuses cached result."""
        subset1 = run_3d.generate_subset_dict(has_new_data=True)
        subset2 = run_3d.generate_subset_dict(has_new_data=False)
        # Same object reference means cache was used
        for key in subset1:
            assert np.array_equal(
                subset1[key].values, subset2[key].values)

    def test_slider_callback_fires_on_new_avg(self, run_4d):
        """update_select_sliders callback fires when averaging changes."""
        slider_updates = []
        run_4d.set_on_sliders_need_update(lambda: slider_updates.append(True))
        run_4d.generate_subset_dict(has_new_data=True)
        assert len(slider_updates) == 1

    def test_select_index_changes_subset(self, run_4d):
        """Changing select_index gives different data slice."""
        subset1 = run_4d.generate_subset_dict(has_new_data=True)
        vals1 = subset1["result_A"].values.copy()
        # Change rep select_index
        rep_dim = run_4d.dim_axis_option['select_value'][0]
        rep_dim.select_index = 2
        subset2 = run_4d.generate_subset_dict(has_new_data=False)
        vals2 = subset2["result_A"].values
        assert not np.array_equal(vals1, vals2)


class TestGenerateSubsetDataset:
    """Test generate_subset returning an xarray Dataset."""

    def test_returns_dataset(self, run_3d):
        """generate_subset returns an xarray Dataset, not a dict."""
        import xarray as xr
        result = run_3d.generate_subset(has_new_data=True)
        assert isinstance(result, xr.Dataset)

    def test_dataset_has_correct_vars(self, run_3d):
        """The Dataset should contain the same variables as the dict version."""
        subset_dict = run_3d.generate_subset_dict(has_new_data=True)
        subset_ds = run_3d.generate_subset(has_new_data=True)
        assert set(subset_ds.data_vars) == set(subset_dict.keys())

    def test_dataset_dims_match_dict(self, run_3d):
        """Dataset variables should have same dims as dict version."""
        subset_dict = run_3d.generate_subset_dict(has_new_data=True)
        subset_ds = run_3d.generate_subset(has_new_data=True)
        for name in subset_dict:
            assert set(subset_ds[name].dims) == set(subset_dict[name].dims)


class TestCacheInvalidation:
    """Test that cache is properly invalidated."""

    def test_cache_invalidated_on_process_run_data(self, run_3d):
        """Calling process_run_data clears the cache."""
        run_3d.generate_subset_dict(has_new_data=True)
        assert run_3d._cached_avg is not None
        run_3d.process_run_data(avg_axis="iteration", result_keywords="")
        assert run_3d._cached_avg is None

    def test_has_new_data_bypasses_cache(self, run_3d):
        """has_new_data=True always recomputes even if cache exists."""
        slider_updates = []
        run_3d.set_on_sliders_need_update(lambda: slider_updates.append(True))
        run_3d.generate_subset_dict(has_new_data=True)
        run_3d.generate_subset_dict(has_new_data=True)
        # Slider callback fires both times (cache bypassed)
        assert len(slider_updates) == 2

    def test_cache_not_recomputed_on_selection_change(self, run_4d):
        """Changing select_index doesn't trigger re-averaging."""
        slider_updates = []
        run_4d.set_on_sliders_need_update(lambda: slider_updates.append(True))
        run_4d.generate_subset_dict(has_new_data=True)
        assert len(slider_updates) == 1
        rep_dim = run_4d.dim_axis_option['select_value'][0]
        rep_dim.select_index = 1
        run_4d.generate_subset_dict(has_new_data=False)
        # No additional slider update — cache was reused
        assert len(slider_updates) == 1

    def test_cache_recomputed_after_dim_role_change(self, run_4d):
        """Changing a dim's role invalidates the expected dims, triggering recompute."""
        slider_updates = []
        run_4d.set_on_sliders_need_update(lambda: slider_updates.append(True))
        run_4d.generate_subset_dict(has_new_data=True)
        # Move rep from select_value to average
        rep_dim = run_4d.dim_axis_option['select_value'][0]
        run_4d.update_subset_dims(rep_dim, 'average')
        run_4d.generate_subset_dict(has_new_data=False)
        # Cache should be recomputed since expected plot dims changed
        assert len(slider_updates) == 2


class TestParseKeywords:
    """Test the _parse_keywords static method."""

    def test_empty_string(self):
        from arbok_inspector.classes.base_run import BaseRun
        assert BaseRun._parse_keywords("") == []

    def test_single_string(self):
        from arbok_inspector.classes.base_run import BaseRun
        assert BaseRun._parse_keywords("'hello'") == ["hello"]

    def test_list_of_strings(self):
        from arbok_inspector.classes.base_run import BaseRun
        result = BaseRun._parse_keywords("['a', 'b']")
        assert result == ['a', 'b']

    def test_list_with_tuple(self):
        from arbok_inspector.classes.base_run import BaseRun
        result = BaseRun._parse_keywords("[('Q1', 'state'), 'feedback']")
        assert ('Q1', 'state') in result
        assert 'feedback' in result

    def test_invalid_syntax_returns_empty(self):
        from arbok_inspector.classes.base_run import BaseRun
        assert BaseRun._parse_keywords("not valid [[[") == []

    def test_none_like_input(self):
        from arbok_inspector.classes.base_run import BaseRun
        assert BaseRun._parse_keywords("None") == [None]


class TestRemoveDimFromRole:
    """Test _remove_dim_from_current_role helper."""

    def test_remove_from_average(self, run_3d):
        """Removing a dim from average clears its option."""
        iteration = run_3d.dim_axis_option['average'][0]
        run_3d._remove_dim_from_current_role(iteration)
        assert iteration.option is None
        assert iteration not in run_3d.dim_axis_option['average']

    def test_remove_from_x_axis(self, run_3d):
        """Removing a dim from x-axis sets that slot to None."""
        x_dim = run_3d.dim_axis_option['x-axis']
        run_3d._remove_dim_from_current_role(x_dim)
        assert x_dim.option is None
        assert run_3d.dim_axis_option['x-axis'] is None

    def test_remove_from_select_value_resets_index(self, run_4d):
        """Removing a dim from select_value resets its select_index to 0."""
        rep_dim = run_4d.dim_axis_option['select_value'][0]
        rep_dim.select_index = 3
        run_4d._remove_dim_from_current_role(rep_dim)
        assert rep_dim.select_index == 0
        assert rep_dim not in run_4d.dim_axis_option['select_value']

    def test_remove_dim_with_none_option(self, run_3d):
        """Removing a dim that has option=None is a safe no-op."""
        from arbok_inspector.classes.dim import Dim
        orphan = Dim("orphan")
        orphan.option = None
        run_3d._remove_dim_from_current_role(orphan)  # should not raise
        assert orphan.option is None


class TestDemoteToSelectValue:
    """Test _demote_to_select_value helper."""

    def test_demotes_and_fires_callback(self, run_3d):
        """Demotion sets option, appends to list, and fires callback."""
        changed = []
        run_3d.set_on_dim_changed(lambda d: changed.append(d))
        x_dim = run_3d.dim_axis_option['x-axis']
        run_3d._demote_to_select_value(x_dim)
        assert x_dim.option == 'select_value'
        assert x_dim in run_3d.dim_axis_option['select_value']
        assert x_dim in changed


class TestUpdateSubsetDimsEdgeCases:
    """Additional edge cases for update_subset_dims."""

    def test_set_same_dim_to_same_role(self, run_3d):
        """Setting a dim to its current role is idempotent."""
        x_dim = run_3d.dim_axis_option['x-axis']
        run_3d.update_subset_dims(x_dim, 'x-axis')
        assert x_dim.option == 'x-axis'
        assert run_3d.dim_axis_option['x-axis'] is x_dim

    def test_swap_x_and_y(self, run_3d):
        """Swapping x and y: set y-dim to x-axis, old x should be demoted."""
        old_x = run_3d.dim_axis_option['x-axis']
        old_y = run_3d.dim_axis_option['y-axis']
        run_3d.update_subset_dims(old_y, 'x-axis')
        assert run_3d.dim_axis_option['x-axis'] is old_y
        assert old_x.option == 'select_value'
        # Now set old_x to y-axis
        run_3d.update_subset_dims(old_x, 'y-axis')
        assert run_3d.dim_axis_option['y-axis'] is old_x
        assert old_x.option == 'y-axis'

    def test_all_dims_to_average(self, run_3d):
        """Moving all dims to average leaves x-axis and y-axis as None."""
        for dim in list(run_3d.dims):
            run_3d.update_subset_dims(dim, 'average')
        assert run_3d.dim_axis_option['x-axis'] is None
        assert run_3d.dim_axis_option['y-axis'] is None
        assert len(run_3d.dim_axis_option['average']) == 3
        assert run_3d.dim_axis_option['select_value'] == []


class TestLoadSweepDict:
    """Test sweep dictionary construction."""

    def test_sweep_dict_has_all_dims(self, run_3d):
        """sweep_dict should have one entry per dataset dimension."""
        assert len(run_3d.sweep_dict) == 3

    def test_parallel_sweep_axes_maps_coords(self, run_3d):
        """parallel_sweep_axes should list dependent coords for each dim index."""
        for i, coords in run_3d.parallel_sweep_axes.items():
            assert isinstance(coords, list)
            assert len(coords) >= 1


class TestGenerateFFTSubset:
    """Test generate_fft_subset for the FFT analysis feature."""

    @staticmethod
    def _find_freq_dim(arr):
        """Find the frequency dimension name (may be 'frequency' or 'fft_frequency')."""
        for d in arr.dims:
            if 'frequency' in d:
                return d
        return None

    def test_no_fft_dim_raises(self, run_3d):
        """Should raise ValueError when no dim is assigned to 'fft' role."""
        with pytest.raises(ValueError, match="No dimension assigned"):
            run_3d.generate_fft_subset()

    def test_fft_replaces_dim_with_frequency(self, run_3d):
        """FFT output should have a frequency dim instead of the FFT dim."""
        iteration_dim = run_3d.dim_axis_option['average'][0]
        run_3d.update_subset_dims(iteration_dim, 'fft')
        result = run_3d.generate_fft_subset()
        for name, arr in result.items():
            freq_dim = self._find_freq_dim(arr)
            assert freq_dim is not None
            assert "iteration" not in arr.dims

    def test_fft_output_is_power_spectrum(self, run_3d):
        """FFT values should be non-negative (|FFT|²)."""
        iteration_dim = run_3d.dim_axis_option['average'][0]
        run_3d.update_subset_dims(iteration_dim, 'fft')
        result = run_3d.generate_fft_subset()
        for name, arr in result.items():
            assert (arr.values >= 0).all()

    def test_fft_freq_range_excludes_dc(self, run_3d):
        """With fft_freq_range starting at index 1, DC should not be present."""
        iteration_dim = run_3d.dim_axis_option['average'][0]
        run_3d.update_subset_dims(iteration_dim, 'fft')
        fft_dim = run_3d.dim_axis_option['fft']
        freq_count = run_3d.full_data_set.sizes[fft_dim.name] // 2 + 1
        run_3d.fft_freq_range = {'min': 1, 'max': freq_count - 1}
        result = run_3d.generate_fft_subset()
        for name, arr in result.items():
            freq_dim = self._find_freq_dim(arr)
            assert 0.0 not in arr.coords[freq_dim].values

    def test_fft_freq_range_includes_dc(self, run_3d):
        """With fft_freq_range starting at index 0, DC should be present."""
        iteration_dim = run_3d.dim_axis_option['average'][0]
        run_3d.update_subset_dims(iteration_dim, 'fft')
        fft_dim = run_3d.dim_axis_option['fft']
        freq_count = run_3d.full_data_set.sizes[fft_dim.name] // 2 + 1
        run_3d.fft_freq_range = {'min': 0, 'max': freq_count - 1}
        result = run_3d.generate_fft_subset()
        for name, arr in result.items():
            freq_dim = self._find_freq_dim(arr)
            assert arr.coords[freq_dim].values[0] == 0.0

    def test_fft_preserves_other_dims(self, run_3d):
        """Non-FFT, non-averaged dims should remain in output."""
        iteration_dim = run_3d.dim_axis_option['average'][0]
        run_3d.update_subset_dims(iteration_dim, 'fft')
        result = run_3d.generate_fft_subset()
        for name, arr in result.items():
            assert "voltage" in arr.dims
            assert "frequency" in arr.dims  # original frequency dim preserved

    def test_fft_with_select_value(self, run_4d):
        """FFT with a select_value dim should apply isel correctly."""
        iteration_dim = run_4d.dim_axis_option['average'][0]
        run_4d.update_subset_dims(iteration_dim, 'fft')
        rep_dim = run_4d.dim_axis_option['select_value'][0]
        rep_dim.select_index = 2
        result = run_4d.generate_fft_subset()
        for name, arr in result.items():
            assert "rep" not in arr.dims
