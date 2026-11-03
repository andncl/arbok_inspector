"""Tests that the fast histogram matches a straightforward np.digitize reference."""
import numpy as np
import pytest

from arbok_inspector.analysis.prepare_data import _vectorized_histogram


def reference_histogram(flat: np.ndarray, bin_edges: np.ndarray) -> np.ndarray:
    """Row-wise histogram with np.digitize semantics (right edge inclusive)."""
    n_bins = len(bin_edges) - 1
    flat_2d = flat.reshape(-1, flat.shape[-1])
    hist = np.zeros((flat_2d.shape[0], n_bins), dtype=np.intp)
    for row, values in enumerate(flat_2d):
        values = values[(values >= bin_edges[0]) & (values <= bin_edges[-1])]
        indices = np.clip(np.digitize(values, bin_edges), 1, n_bins) - 1
        np.add.at(hist[row], indices, 1)
    return hist.reshape(flat.shape[:-1] + (n_bins,))


class TestVectorizedHistogram:

    def test_matches_reference_random(self):
        rng = np.random.default_rng(1)
        flat = rng.standard_normal((4, 6, 500))
        edges = np.linspace(-2, 2, 52)
        np.testing.assert_array_equal(
            _vectorized_histogram(flat, edges), reference_histogram(flat, edges))

    def test_values_exactly_on_edges(self):
        """Values sitting on bin edges must land in the same bin as digitize."""
        edges = np.linspace(-0.3, 0.7, 52)
        flat = np.tile(edges, (3, 4))
        np.testing.assert_array_equal(
            _vectorized_histogram(flat, edges), reference_histogram(flat, edges))

    def test_right_edge_in_last_bin(self):
        edges = np.linspace(0, 1, 11)
        hist = _vectorized_histogram(np.array([[1.0, 0.0]]), edges)
        assert hist[0, -1] == 1
        assert hist[0, 0] == 1

    def test_nan_and_inf_are_ignored(self):
        edges = np.linspace(-1, 1, 5)
        flat = np.array([[np.nan, np.inf, -np.inf, 0.1, 5.0, -5.0]])
        hist = _vectorized_histogram(flat, edges)
        assert hist.sum() == 1

    def test_integer_input(self):
        edges = np.linspace(-0.5, 3.5, 5)
        flat = np.array([[0, 1, 1, 2, 3, 3, 3]])
        np.testing.assert_array_equal(
            _vectorized_histogram(flat, edges)[0], [1, 2, 1, 3])

    @pytest.mark.parametrize("edges", [
        np.array([-1.0, -0.2, 0.0, 0.1, 1.5]),
        np.array([0.0, 1.0, 10.0, 100.0]),
    ])
    def test_non_uniform_edges(self, edges):
        rng = np.random.default_rng(2)
        flat = rng.uniform(-2, 120, size=(5, 300))
        flat[0, :len(edges)] = edges
        np.testing.assert_array_equal(
            _vectorized_histogram(flat, edges), reference_histogram(flat, edges))

    def test_output_shape_and_dtype(self):
        flat = np.zeros((2, 3, 7))
        hist = _vectorized_histogram(flat, np.linspace(-1, 1, 11))
        assert hist.shape == (2, 3, 10)
        assert np.issubdtype(hist.dtype, np.integer)
