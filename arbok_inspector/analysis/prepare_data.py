"""Data preparation utilities: averaging and histogram binning."""
from math import prod

from qcodes.dataset.data_set import load_by_id, DataSet
import xarray as xr
import numpy as np


def prepare_and_avg_data(
    run: int | DataSet | xr.Dataset | xr.DataArray,
    readout_name: str,
    avg_axes: str | list = 'auto'
) -> tuple[int | None, xr.DataArray, np.ndarray]:
    """
    Normalize input to (run_id, xr.DataArray, np.ndarray) regardless of input type.
    Optionally averages over specified axes.

    Args:
        run: Run id, qcodes DataSet, xarray Dataset or DataArray
        readout_name: Name of the readout variable
        avg_axes: Axes to average over ('auto' = all with 'iteration' in name)
    """
    xdata_array = None
    if avg_axes is None:
        avg_axes = []
    if isinstance(run, int):
        data = load_by_id(run)
        xdataset = data.to_xarray_dataset()
        run_id = run
    elif isinstance(run, DataSet):
        data = run
        run_id = data.run_id
        xdataset = data.to_xarray_dataset()
    elif isinstance(run, xr.Dataset):
        xdataset = run
        run_id = xdataset.attrs.get('run_id')
    elif isinstance(run, xr.DataArray):
        xdataset = None
        xdata_array = run
        run_id = None
    else:
        raise ValueError(
            f"Invalid input type for run. Must be int, DataSet, xr.Dataset or "
            f"xr.DataArray. Got {type(run)}"
        )
    if xdataset is not None:
        if readout_name not in xdataset.data_vars:
            readout_name = find_data_variable_from_keyword(xdataset, readout_name)
        xdata_array = xdataset[readout_name]
    xdata_array = avg_dataarray(xdata_array, avg_axes)
    np_data = xdata_array.to_numpy()
    return run_id, xdata_array, np_data


def find_data_variable_from_keyword(
        xdataset: xr.Dataset, keyword: str | tuple) -> str:
    """
    Find a unique data variable matching the keyword(s).

    Args:
        xdataset: Dataset to search
        keyword: String (substring match) or tuple of strings (all must match)
    Returns:
        The matching variable name
    Raises:
        ValueError if zero or multiple matches
    """
    if isinstance(keyword, str):
        keyword = (keyword,)
    if not isinstance(keyword, tuple):
        raise ValueError(f"Keyword must be a string or tuple. Got {type(keyword)}")
    matches = [
        var for var in xdataset.data_vars
        if all(subkey in str(var) for subkey in keyword)
    ]
    if len(matches) == 0:
        raise ValueError(
            f"No data variable found for keyword {keyword}. "
            f"Available: {list(xdataset.data_vars)}"
        )
    if len(matches) > 1:
        raise ValueError(
            f"Multiple data variables match keyword {keyword}: "
            f"{[str(v) for v in matches]}"
        )
    return matches[0]


def avg_dataarray(xdata_array: xr.DataArray, avg_axes: str | list = 'auto') -> xr.DataArray:
    """
    Average the DataArray over the specified dimensions.

    Args:
        xdata_array: Data to average
        avg_axes: 'auto' (all dims with 'iteration'), a dim name, or list of dim names
    """
    if avg_axes is None:
        avg_axes = []
    if isinstance(avg_axes, str):
        if avg_axes == 'auto':
            avg_axes = [dim for dim in xdata_array.dims if 'iteration' in dim]
        else:
            avg_axes = [avg_axes]
    for axis in avg_axes:
        if axis not in xdata_array.dims:
            raise KeyError(f"Dimension '{axis}' not found in DataArray (has: {list(xdata_array.dims)})")
        xdata_array = xdata_array.mean(axis)
    return xdata_array


def bin_over_axis(
    data: xr.DataArray,
    dim: list[str],
    bins: int | list = 51,
) -> xr.DataArray:
    """
    Bin (histogram) data over the specified dimensions.

    The specified dims are collapsed into a histogram. The result has all
    non-binned dims preserved, plus a new 'Current' dim for bin centers.

    Args:
        data: Input DataArray
        dim: Dimension name(s) to bin over
        bins: Number of bins (int) or explicit bin edges (array-like)
    Returns:
        DataArray with dims = [non-binned dims...] + ['Current']
    Raises:
        ValueError: If dim list is empty or contains names not in data.dims
    """
    if isinstance(dim, str):
        dim = [dim]
    if not dim:
        raise ValueError("Must specify at least one dimension to bin over")

    missing = [d for d in dim if d not in data.dims]
    if missing:
        raise ValueError(
            f"Dimensions {missing} not found in data (has: {list(data.dims)})"
        )

    kept_dims = [d for d in data.dims if d not in dim]
    axes_to_bin = [data.get_axis_num(d) for d in dim]

    data_np = data.values.copy()

    # Handle arbok sentinel dimensions (last value is padding)
    arbok_axes = sorted(
        [data.get_axis_num(d) for d in dim if 'arbok' in d],
        reverse=True
    )
    for ax in arbok_axes:
        data_np = np.take(data_np, range(data_np.shape[ax] - 1), axis=ax)
        # Recompute axis positions after slicing (shape unchanged for other axes)

    # Recompute axes_to_bin after potential slicing
    # Since we only sliced along arbok axes (which are within axes_to_bin),
    # the axis indices haven't shifted — only the sizes changed.

    # Move bin axes to the end
    n_bin_axes = len(axes_to_bin)
    dest_axes = list(range(data_np.ndim - n_bin_axes, data_np.ndim))
    data_np = np.moveaxis(data_np, axes_to_bin, dest_axes)

    # Shape: (*kept_shape, *bin_shape)
    kept_shape = data_np.shape[:-n_bin_axes]
    n_samples = prod(data_np.shape[-n_bin_axes:])

    # Flatten the bin axes into one
    flat = data_np.reshape(kept_shape + (n_samples,))

    # Compute bin edges
    bin_edges = _compute_bin_edges(flat, bins)
    n_bins = len(bin_edges) - 1

    # Vectorized histogram using searchsorted
    hist = _vectorized_histogram(flat, bin_edges)
    hist = hist.reshape(kept_shape + (n_bins,))

    # Build output coordinates
    new_dims = kept_dims + ['Current']
    coords = {d: data.coords[d] for d in kept_dims if d in data.coords}
    coords['Current'] = (bin_edges[:-1] + bin_edges[1:]) / 2

    return xr.DataArray(hist, dims=new_dims, coords=coords)


def _compute_bin_edges(flat: np.ndarray, bins: int | list | np.ndarray) -> np.ndarray:
    """Compute histogram bin edges, handling NaN values."""
    if not isinstance(bins, int):
        return np.asarray(bins, dtype=float)

    valid = flat[np.isfinite(flat)]
    if valid.size == 0:
        return np.linspace(0, 1, bins + 1)

    mean = valid.mean()
    std = valid.std()
    if std == 0:
        return np.linspace(mean - 0.5, mean + 0.5, bins + 1)
    return np.linspace(mean - 3 * std, mean + 3 * std, bins + 1)


def _vectorized_histogram(flat: np.ndarray, bin_edges: np.ndarray) -> np.ndarray:
    """
    Compute histograms along the last axis of `flat` using vectorized ops.
    Much faster than np.apply_along_axis for large arrays.

    Args:
        flat: Array of shape (*batch, n_samples)
        bin_edges: 1D array of bin edges
    Returns:
        Array of shape (*batch, n_bins)
    """
    batch_shape = flat.shape[:-1]
    n_samples = flat.shape[-1]
    n_bins = len(bin_edges) - 1

    # Flatten batch dimensions for processing
    flat_2d = flat.reshape(-1, n_samples)
    n_rows = flat_2d.shape[0]

    # Use digitize to assign each value to a bin
    # Replace NaN with a value that maps outside bins
    work = flat_2d.copy()
    nan_mask = ~np.isfinite(work)
    work[nan_mask] = bin_edges[0] - 1  # maps to bin 0 (out of range)

    indices = np.digitize(work, bin_edges)  # values 0..n_bins+1
    # Clip to valid bin range: bins are 1..n_bins, 0 and n_bins+1 are out-of-range
    indices = np.clip(indices, 1, n_bins) - 1  # now 0..n_bins-1

    # Zero out contributions from NaN and out-of-range values
    in_range = (work >= bin_edges[0]) & (work <= bin_edges[-1]) & (~nan_mask)

    # Build histogram via scatter-add
    hist = np.zeros((n_rows, n_bins), dtype=np.intp)
    row_idx = np.arange(n_rows)[:, np.newaxis]
    # Use np.add.at for unbuffered in-place addition
    np.add.at(hist, (np.broadcast_to(row_idx, flat_2d.shape)[in_range],
                     indices[in_range]), 1)

    return hist.reshape(batch_shape + (n_bins,))
