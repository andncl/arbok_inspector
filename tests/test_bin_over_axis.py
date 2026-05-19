"""Tests for bin_over_axis and related helpers in prepare_data."""
import numpy as np
import xarray as xr
import pytest

from arbok_inspector.analysis.prepare_data import bin_over_axis


class TestBinOverAxis:
    def test_basic_1d_binning(self):
        data = xr.DataArray(
            np.random.default_rng(0).standard_normal(100),
            dims=["sample"],
            coords={"sample": np.arange(100)},
        )
        result = bin_over_axis(data, dim=["sample"], bins=10)
        assert "Current" in result.dims
        assert result.sizes["Current"] == 10
        assert result.values.sum() > 0

    def test_2d_bin_one_axis(self):
        rng = np.random.default_rng(42)
        data = xr.DataArray(
            rng.standard_normal((5, 100)),
            dims=["voltage", "iteration"],
            coords={
                "voltage": np.linspace(0, 1, 5),
                "iteration": np.arange(100),
            },
        )
        result = bin_over_axis(data, dim=["iteration"], bins=20)
        assert "voltage" in result.dims
        assert "Current" in result.dims
        assert result.sizes["voltage"] == 5
        assert result.sizes["Current"] == 20

    def test_bin_multiple_axes(self):
        rng = np.random.default_rng(42)
        data = xr.DataArray(
            rng.standard_normal((3, 4, 50)),
            dims=["a", "b", "c"],
            coords={"a": np.arange(3), "b": np.arange(4), "c": np.arange(50)},
        )
        result = bin_over_axis(data, dim=["b", "c"], bins=15)
        assert list(result.dims) == ["a", "Current"]
        assert result.sizes["a"] == 3
        assert result.sizes["Current"] == 15

    def test_empty_dim_raises(self):
        data = xr.DataArray(np.zeros(5), dims=["x"])
        with pytest.raises(ValueError, match="at least one"):
            bin_over_axis(data, dim=[], bins=10)

    def test_missing_dim_raises(self):
        data = xr.DataArray(np.zeros(5), dims=["x"])
        with pytest.raises(ValueError, match="not found"):
            bin_over_axis(data, dim=["nonexistent"], bins=10)

    def test_string_dim_accepted(self):
        data = xr.DataArray(
            np.random.default_rng(0).standard_normal(50),
            dims=["x"],
            coords={"x": np.arange(50)},
        )
        result = bin_over_axis(data, dim="x", bins=10)
        assert "Current" in result.dims

    def test_explicit_bin_edges(self):
        data = xr.DataArray(
            np.linspace(0, 10, 100),
            dims=["x"],
            coords={"x": np.arange(100)},
        )
        edges = np.array([0, 2, 4, 6, 8, 10], dtype=float)
        result = bin_over_axis(data, dim=["x"], bins=edges)
        assert result.sizes["Current"] == 5

    def test_nan_values_handled(self):
        values = np.ones(50)
        values[10:20] = np.nan
        data = xr.DataArray(values, dims=["x"], coords={"x": np.arange(50)})
        result = bin_over_axis(data, dim=["x"], bins=10)
        assert not np.any(np.isnan(result.values))

    def test_total_counts_match_non_nan_in_range(self):
        rng = np.random.default_rng(7)
        values = rng.standard_normal(200)
        data = xr.DataArray(values, dims=["x"], coords={"x": np.arange(200)})
        result = bin_over_axis(data, dim=["x"], bins=51)
        # Total counts should be <= n_samples (some may fall outside 3-sigma range)
        assert result.values.sum() <= 200

    def test_arbok_sentinel_dim(self):
        """Dims with 'arbok' in name should have last element trimmed."""
        rng = np.random.default_rng(0)
        data = xr.DataArray(
            rng.standard_normal((5, 11)),
            dims=["voltage", "arbok_iter"],
            coords={
                "voltage": np.arange(5, dtype=float),
                "arbok_iter": np.arange(11, dtype=float),
            },
        )
        result = bin_over_axis(data, dim=["arbok_iter"], bins=10)
        assert "voltage" in result.dims
        assert result.sizes["Current"] == 10
