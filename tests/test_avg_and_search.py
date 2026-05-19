"""Tests for avg_dataarray and find_data_variable_from_keyword in prepare_data."""
import numpy as np
import xarray as xr
import pytest

from arbok_inspector.analysis.prepare_data import (
    avg_dataarray,
    find_data_variable_from_keyword,
)


class TestAvgDataarray:
    def test_auto_averages_iteration_dims(self):
        data = xr.DataArray(
            np.ones((10, 5)),
            dims=["iteration", "voltage"],
        )
        result = avg_dataarray(data, avg_axes="auto")
        assert "iteration" not in result.dims
        assert "voltage" in result.dims

    def test_auto_no_iteration_dims(self):
        data = xr.DataArray(np.ones((3, 4)), dims=["voltage", "frequency"])
        result = avg_dataarray(data, avg_axes="auto")
        assert list(result.dims) == ["voltage", "frequency"]

    def test_explicit_single_axis(self):
        data = xr.DataArray(np.ones((10, 5)), dims=["rep", "voltage"])
        result = avg_dataarray(data, avg_axes="rep")
        assert "rep" not in result.dims
        assert result.shape == (5,)

    def test_explicit_list_of_axes(self):
        data = xr.DataArray(np.ones((3, 4, 5)), dims=["a", "b", "c"])
        result = avg_dataarray(data, avg_axes=["a", "b"])
        assert list(result.dims) == ["c"]

    def test_none_averages_nothing(self):
        data = xr.DataArray(np.ones((3, 4)), dims=["a", "b"])
        result = avg_dataarray(data, avg_axes=None)
        assert list(result.dims) == ["a", "b"]

    def test_missing_axis_raises(self):
        data = xr.DataArray(np.ones(5), dims=["x"])
        with pytest.raises(KeyError, match="not found"):
            avg_dataarray(data, avg_axes="nonexistent")

    def test_mean_values_correct(self):
        data = xr.DataArray(
            np.arange(20, dtype=float).reshape(4, 5),
            dims=["iteration", "voltage"],
        )
        result = avg_dataarray(data, avg_axes="iteration")
        expected = data.mean("iteration")
        np.testing.assert_array_almost_equal(result.values, expected.values)


class TestFindDataVariableFromKeyword:
    def make_dataset(self):
        return xr.Dataset({
            "qubit__readout__I": (["x"], np.zeros(5)),
            "qubit__readout__Q": (["x"], np.zeros(5)),
            "resonator__signal": (["x"], np.zeros(5)),
        })

    def test_single_keyword_match(self):
        ds = self.make_dataset()
        assert find_data_variable_from_keyword(ds, "resonator") == "resonator__signal"

    def test_tuple_keyword_match(self):
        ds = self.make_dataset()
        result = find_data_variable_from_keyword(ds, ("readout", "I"))
        assert result == "qubit__readout__I"

    def test_no_match_raises(self):
        ds = self.make_dataset()
        with pytest.raises(ValueError, match="No data variable"):
            find_data_variable_from_keyword(ds, "nonexistent")

    def test_multiple_matches_raises(self):
        ds = self.make_dataset()
        with pytest.raises(ValueError, match="Multiple"):
            find_data_variable_from_keyword(ds, "readout")

    def test_invalid_keyword_type_raises(self):
        ds = self.make_dataset()
        with pytest.raises(ValueError, match="string or tuple"):
            find_data_variable_from_keyword(ds, ["list", "not", "allowed"])
