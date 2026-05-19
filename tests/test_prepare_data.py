"""Tests for the prepare_data module: averaging and histogram binning."""
import numpy as np
import xarray as xr
import pytest

from arbok_inspector.analysis.prepare_data import (
    avg_dataarray,
    bin_over_axis,
    find_data_variable_from_keyword,
    _compute_bin_edges,
    _vectorized_histogram,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def simple_3d_array():
    """3D DataArray: iteration(10) x voltage(5) x frequency(20)."""
    rng = np.random.default_rng(42)
    data = rng.standard_normal((10, 5, 20))
    return xr.DataArray(
        data,
        dims=["iteration", "voltage", "frequency"],
        coords={
            "iteration": np.arange(10),
            "voltage": np.linspace(0, 1, 5),
            "frequency": np.linspace(1e9, 5e9, 20),
        },
    )


@pytest.fixture
def simple_2d_array():
    """2D DataArray: voltage(5) x frequency(20)."""
    rng = np.random.default_rng(42)
    data = rng.standard_normal((5, 20))
    return xr.DataArray(
        data,
        dims=["voltage", "frequency"],
        coords={
            "voltage": np.linspace(0, 1, 5),
            "frequency": np.linspace(1e9, 5e9, 20),
        },
    )


@pytest.fixture
def array_with_arbok_dim():
    """3D array with an 'arbok_iteration' dim (has padding in last index)."""
    rng = np.random.default_rng(42)
    data = rng.standard_normal((11, 5, 20))
    # Last slice along arbok_iteration is padding
    data[-1, :, :] = 999.0
    return xr.DataArray(
        data,
        dims=["arbok_iteration", "voltage", "frequency"],
        coords={
            "arbok_iteration": np.arange(11),
            "voltage": np.linspace(0, 1, 5),
            "frequency": np.linspace(1e9, 5e9, 20),
        },
    )


@pytest.fixture
def array_with_nans():
    """2D array with NaN values."""
    data = np.array([[1.0, 2.0, np.nan, 4.0, 5.0],
                     [np.nan, np.nan, 3.0, 3.0, 3.0]])
    return xr.DataArray(
        data,
        dims=["batch", "sample"],
        coords={"batch": [0, 1], "sample": np.arange(5)},
    )


# ─── Tests for avg_dataarray ─────────────────────────────────────────────────

class TestAvgDataarray:
    def test_auto_averages_iteration(self, simple_3d_array):
        result = avg_dataarray(simple_3d_array, 'auto')
        assert "iteration" not in result.dims
        assert "voltage" in result.dims
        assert "frequency" in result.dims

    def test_explicit_single_axis(self, simple_3d_array):
        result = avg_dataarray(simple_3d_array, 'voltage')
        assert "voltage" not in result.dims
        assert "iteration" in result.dims

    def test_explicit_list(self, simple_3d_array):
        result = avg_dataarray(simple_3d_array, ['iteration', 'voltage'])
        assert set(result.dims) == {"frequency"}

    def test_none_means_no_averaging(self, simple_3d_array):
        result = avg_dataarray(simple_3d_array, None)
        assert set(result.dims) == {"iteration", "voltage", "frequency"}

    def test_empty_list_means_no_averaging(self, simple_3d_array):
        result = avg_dataarray(simple_3d_array, [])
        assert set(result.dims) == {"iteration", "voltage", "frequency"}

    def test_invalid_axis_raises(self, simple_3d_array):
        with pytest.raises(KeyError, match="nonexistent"):
            avg_dataarray(simple_3d_array, 'nonexistent')

    def test_auto_no_iteration_dim(self, simple_2d_array):
        """Auto with no iteration dim does nothing."""
        result = avg_dataarray(simple_2d_array, 'auto')
        assert set(result.dims) == {"voltage", "frequency"}


# ─── Tests for bin_over_axis ──────────────────────────────────────────────────

class TestBinOverAxis:
    def test_basic_binning_shape(self, simple_3d_array):
        """Binning over iteration: result has (voltage, frequency, Current)."""
        result = bin_over_axis(simple_3d_array, dim=["iteration"], bins=20)
        assert set(result.dims) == {"voltage", "frequency", "Current"}
        assert result.sizes["Current"] == 20
        assert result.sizes["voltage"] == 5
        assert result.sizes["frequency"] == 20

    def test_bin_over_multiple_dims(self, simple_3d_array):
        """Binning over iteration + voltage collapses both."""
        result = bin_over_axis(simple_3d_array, dim=["iteration", "voltage"], bins=15)
        assert set(result.dims) == {"frequency", "Current"}
        assert result.sizes["Current"] == 15
        assert result.sizes["frequency"] == 20

    def test_bin_counts_sum_to_samples(self, simple_3d_array):
        """Total histogram counts should equal number of samples binned."""
        result = bin_over_axis(simple_3d_array, dim=["iteration"], bins=50)
        # For each (voltage, frequency) cell, sum of bins ≈ 10 (iteration size)
        # Some may fall outside ±3σ, so check >= 90%
        total_counts = result.sum(dim="Current")
        expected = simple_3d_array.sizes["iteration"]
        assert (total_counts >= expected * 0.9).all()

    def test_string_dim_input(self, simple_3d_array):
        """Single string dim is accepted."""
        result = bin_over_axis(simple_3d_array, dim="iteration", bins=10)
        assert "Current" in result.dims

    def test_explicit_bin_edges(self, simple_3d_array):
        """Explicit bin edges are used as-is."""
        edges = np.linspace(-3, 3, 31)
        result = bin_over_axis(simple_3d_array, dim=["iteration"], bins=edges)
        assert result.sizes["Current"] == 30

    def test_current_coord_is_bin_centers(self, simple_3d_array):
        """The 'Current' coordinate should be bin centers, not edges."""
        edges = np.array([0.0, 1.0, 2.0, 3.0])
        result = bin_over_axis(simple_3d_array, dim=["iteration"], bins=edges)
        expected_centers = np.array([0.5, 1.5, 2.5])
        np.testing.assert_allclose(result.coords["Current"].values, expected_centers)

    def test_empty_dim_raises(self, simple_3d_array):
        with pytest.raises(ValueError, match="at least one dimension"):
            bin_over_axis(simple_3d_array, dim=[], bins=10)

    def test_missing_dim_raises(self, simple_3d_array):
        with pytest.raises(ValueError, match="not found"):
            bin_over_axis(simple_3d_array, dim=["nonexistent"], bins=10)

    def test_preserves_non_binned_coords(self, simple_3d_array):
        """Non-binned dimension coordinates should be preserved."""
        result = bin_over_axis(simple_3d_array, dim=["iteration"], bins=10)
        np.testing.assert_array_equal(
            result.coords["voltage"].values,
            simple_3d_array.coords["voltage"].values,
        )
        np.testing.assert_array_equal(
            result.coords["frequency"].values,
            simple_3d_array.coords["frequency"].values,
        )

    def test_arbok_dim_strips_last_value(self, array_with_arbok_dim):
        """Arbok dims have a padding value in the last index that should be stripped."""
        result = bin_over_axis(array_with_arbok_dim, dim=["arbok_iteration"], bins=20)
        assert set(result.dims) == {"voltage", "frequency", "Current"}
        # The padding value (999) should not dominate the histogram
        # The bin centers should be roughly centered on the actual data (std normal)
        centers = result.coords["Current"].values
        assert centers.max() < 100  # not near 999

    def test_nan_handling(self, array_with_nans):
        """NaN values should not contribute to histogram counts."""
        result = bin_over_axis(array_with_nans, dim=["sample"], bins=10)
        assert set(result.dims) == {"batch", "Current"}
        # First batch has 4 valid values, second has 3
        counts_batch_0 = result.sel(batch=0).sum().item()
        counts_batch_1 = result.sel(batch=1).sum().item()
        assert counts_batch_0 <= 4
        assert counts_batch_1 <= 3

    def test_all_nan_produces_valid_output(self):
        """All-NaN data should produce zero-count histogram, not crash."""
        data = xr.DataArray(
            np.full((3, 5), np.nan),
            dims=["a", "b"],
            coords={"a": [0, 1, 2], "b": np.arange(5)},
        )
        result = bin_over_axis(data, dim=["b"], bins=10)
        assert result.sum().item() == 0
        assert result.sizes["Current"] == 10

    def test_constant_data(self):
        """Constant data (std=0) should not produce NaN bin edges."""
        data = xr.DataArray(
            np.ones((4, 10)),
            dims=["batch", "sample"],
            coords={"batch": np.arange(4), "sample": np.arange(10)},
        )
        result = bin_over_axis(data, dim=["sample"], bins=10)
        assert not np.any(np.isnan(result.coords["Current"].values))
        assert result.sum().item() > 0

    def test_single_element_dim(self):
        """Binning over a dim of size 1 should work."""
        data = xr.DataArray(
            np.array([[5.0, 3.0, 7.0]]),
            dims=["single", "x"],
            coords={"single": [0], "x": [0, 1, 2]},
        )
        result = bin_over_axis(data, dim=["single"], bins=5)
        assert result.sizes["Current"] == 5
        assert result.sizes["x"] == 3


# ─── Tests for _compute_bin_edges ────────────────────────────────────────────

class TestComputeBinEdges:
    def test_normal_data(self):
        rng = np.random.default_rng(42)
        flat = rng.standard_normal((10, 100))
        edges = _compute_bin_edges(flat, bins=20)
        assert len(edges) == 21
        assert edges[0] < edges[-1]

    def test_all_nan(self):
        flat = np.full((5, 10), np.nan)
        edges = _compute_bin_edges(flat, bins=10)
        assert len(edges) == 11
        assert not np.any(np.isnan(edges))

    def test_zero_std(self):
        flat = np.ones((3, 10)) * 5.0
        edges = _compute_bin_edges(flat, bins=10)
        assert len(edges) == 11
        assert edges[0] < 5.0 < edges[-1]

    def test_explicit_edges_passthrough(self):
        edges_in = np.array([0, 1, 2, 3, 4])
        edges_out = _compute_bin_edges(np.zeros((2, 5)), edges_in)
        np.testing.assert_array_equal(edges_in, edges_out)


# ─── Tests for _vectorized_histogram ─────────────────────────────────────────

class TestVectorizedHistogram:
    def test_matches_numpy_histogram(self):
        """Vectorized histogram should match np.histogram for each row."""
        rng = np.random.default_rng(42)
        flat = rng.standard_normal((5, 100))
        edges = np.linspace(-3, 3, 21)
        result = _vectorized_histogram(flat, edges)
        for i in range(5):
            expected, _ = np.histogram(flat[i], bins=edges)
            np.testing.assert_array_equal(result[i], expected)

    def test_nan_excluded(self):
        """NaN values should not contribute to any bin."""
        flat = np.array([[1.0, 2.0, np.nan, 4.0]])
        edges = np.array([0, 2.5, 5.0])
        result = _vectorized_histogram(flat, edges)
        # Bin [0, 2.5): values 1, 2 → count 2
        # Bin [2.5, 5.0]: value 4 → count 1
        assert result[0, 0] == 2
        assert result[0, 1] == 1

    def test_out_of_range_excluded(self):
        """Values outside bin edges should not be counted."""
        flat = np.array([[-10.0, 0.5, 1.5, 100.0]])
        edges = np.array([0.0, 1.0, 2.0])
        result = _vectorized_histogram(flat, edges)
        assert result[0, 0] == 1  # 0.5
        assert result[0, 1] == 1  # 1.5
        assert result.sum() == 2

    def test_batch_shape_preserved(self):
        """Output batch dimensions should match input."""
        rng = np.random.default_rng(42)
        flat = rng.standard_normal((3, 4, 50))
        edges = np.linspace(-3, 3, 11)
        result = _vectorized_histogram(flat, edges)
        assert result.shape == (3, 4, 10)


# ─── Tests for find_data_variable_from_keyword ────────────────────────────────

class TestFindDataVariable:
    @pytest.fixture
    def dataset(self):
        return xr.Dataset({
            "readout__I": (["x"], [1, 2, 3]),
            "readout__Q": (["x"], [4, 5, 6]),
            "feedback_signal": (["x"], [7, 8, 9]),
        })

    def test_string_match(self, dataset):
        assert find_data_variable_from_keyword(dataset, "feedback") == "feedback_signal"

    def test_tuple_match(self, dataset):
        result = find_data_variable_from_keyword(dataset, ("readout", "I"))
        assert result == "readout__I"

    def test_no_match_raises(self, dataset):
        with pytest.raises(ValueError, match="No data variable"):
            find_data_variable_from_keyword(dataset, "nonexistent")

    def test_multiple_matches_raises(self, dataset):
        with pytest.raises(ValueError, match="Multiple"):
            find_data_variable_from_keyword(dataset, "readout")


# ─── Tests for compute_fft ──────────────────────────────────────────────────

class TestComputeFFT:
    from arbok_inspector.analysis.prepare_data import compute_fft

    @pytest.fixture
    def sine_array(self):
        """1D DataArray containing a pure sine wave at 5 Hz."""
        t = np.linspace(0, 1, 100, endpoint=False)
        data = np.sin(2 * np.pi * 5 * t)
        return xr.DataArray(data, dims=["time"], coords={"time": t})

    @pytest.fixture
    def sine_2d_array(self):
        """2D DataArray: voltage(3) x time(100) with sine at 5 Hz."""
        t = np.linspace(0, 1, 100, endpoint=False)
        voltages = [0.0, 0.5, 1.0]
        data = np.array([np.sin(2 * np.pi * 5 * t) for _ in voltages])
        return xr.DataArray(
            data, dims=["voltage", "time"],
            coords={"voltage": voltages, "time": t},
        )

    def test_output_dims_replace_fft_dim(self, sine_array):
        from arbok_inspector.analysis.prepare_data import compute_fft
        result = compute_fft(sine_array, dim="time")
        assert "frequency" in result.dims
        assert "time" not in result.dims

    def test_peak_at_correct_frequency(self, sine_array):
        from arbok_inspector.analysis.prepare_data import compute_fft
        result = compute_fft(sine_array, dim="time")
        freqs = result.coords["frequency"].values
        # Skip DC component at index 0
        peak_idx = int(result.values[1:].argmax()) + 1
        assert abs(freqs[peak_idx] - 5.0) < 1.5

    def test_includes_dc_by_default(self, sine_array):
        from arbok_inspector.analysis.prepare_data import compute_fft
        result = compute_fft(sine_array, dim="time")
        assert result.coords["frequency"].values[0] == 0.0

    def test_representation_amplitude(self, sine_array):
        from arbok_inspector.analysis.prepare_data import compute_fft
        result = compute_fft(sine_array, dim="time", representation='Amplitude')
        assert (result.values >= 0).all()

    def test_representation_real(self, sine_array):
        from arbok_inspector.analysis.prepare_data import compute_fft
        result = compute_fft(sine_array, dim="time", representation='Real')
        assert "frequency" in result.dims

    def test_representation_imaginary(self, sine_array):
        from arbok_inspector.analysis.prepare_data import compute_fft
        result = compute_fft(sine_array, dim="time", representation='Imaginary')
        assert "frequency" in result.dims

    def test_2d_fft_preserves_other_dim(self, sine_2d_array):
        from arbok_inspector.analysis.prepare_data import compute_fft
        result = compute_fft(sine_2d_array, dim="time")
        assert "voltage" in result.dims
        assert "frequency" in result.dims
        assert result.sizes["voltage"] == 3

    def test_invalid_dim_raises(self, sine_array):
        from arbok_inspector.analysis.prepare_data import compute_fft
        with pytest.raises(ValueError, match="not found"):
            compute_fft(sine_array, dim="nonexistent")

    def test_size_1_dim_raises(self):
        from arbok_inspector.analysis.prepare_data import compute_fft
        data = xr.DataArray([1.0], dims=["x"], coords={"x": [0.0]})
        with pytest.raises(ValueError, match="at least 2"):
            compute_fft(data, dim="x")

    def test_output_values_are_power(self, sine_array):
        from arbok_inspector.analysis.prepare_data import compute_fft
        result = compute_fft(sine_array, dim="time")
        assert (result.values >= 0).all()
