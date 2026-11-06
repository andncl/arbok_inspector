"""Data preparation utilities: averaging, histogram binning, FFT and decay spectra."""
from math import prod

from qcodes.dataset.data_set import load_by_id, DataSet
from scipy.optimize import nnls
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


FFT_REPRESENTATIONS = ['PSD', 'Amplitude', 'Real', 'Imaginary']


def compute_fft(
    data: xr.DataArray,
    dim: str,
    representation: str = 'PSD',
) -> xr.DataArray:
    """
    Compute FFT along a single dimension and return the chosen representation.

    Args:
        data: Input DataArray
        dim: Dimension name to FFT along
        representation: One of 'PSD' (|FFT|²), 'Amplitude' (|FFT|),
                        'Real' (Re(FFT)), 'Imaginary' (Im(FFT))
    Returns:
        DataArray with dim replaced by 'frequency' (name stored in
        attrs['spectrum_dim'], it gets a prefix if 'frequency' is taken)
    Raises:
        ValueError: If dim is not in data.dims or has fewer than 2 points
    """
    if dim not in data.dims:
        raise ValueError(f"Dimension '{dim}' not found in data (has: {list(data.dims)})")
    n = data.sizes[dim]
    if n < 2:
        raise ValueError(f"Dimension '{dim}' has size {n}, need at least 2 for FFT")

    coord_values = data.coords[dim].values
    dt = np.abs(np.diff(coord_values).mean())
    if dt == 0:
        dt = 1.0
    freqs = np.fft.rfftfreq(n, d=dt)

    fft_vals = np.fft.rfft(data.values, axis=data.get_axis_num(dim))

    if representation == 'Real':
        output = fft_vals.real
    elif representation == 'Imaginary':
        output = fft_vals.imag
    elif representation == 'Amplitude':
        output = np.abs(fft_vals)
    else:
        output = np.abs(fft_vals) ** 2

    freq_dim = 'frequency'
    existing_dims = set(d for d in data.dims if d != dim)
    existing_coords = set(data.coords) - {dim}
    while freq_dim in existing_dims or freq_dim in existing_coords:
        freq_dim = 'fft_' + freq_dim

    new_dims = [d if d != dim else freq_dim for d in data.dims]
    coords = {d: data.coords[d] for d in data.dims if d != dim and d in data.coords}
    coords[freq_dim] = freqs

    return xr.DataArray(output, dims=new_dims, coords=coords,
                        attrs={"spectrum_dim": freq_dim})


DECAY_TIME_POINTS = 100
DECAY_REGULARIZATION = 0.0025


def compute_decay_spectrum(
    data: xr.DataArray,
    dim: str,
    n_points: int = DECAY_TIME_POINTS,
    regularization: float = DECAY_REGULARIZATION,
) -> xr.DataArray:
    """
    Decay-time spectrum along one dimension (regularised inverse Laplace transform).

    Each trace f(t) is modelled as  offset + sum_j g_j * exp(-(t - t0) / tau_j)
    on a log-spaced grid of decay times tau_j and solved for g_j >= 0 with
    `scipy.optimize.nnls` plus Tikhonov regularisation. The brightest point
    is the dominant decay time, its value roughly the decay amplitude.
    Rising traces (f[first] < f[last]) are flipped, so rises and decays from
    or towards any baseline give the same positive spectrum. Oscillating
    decays are not representable by real exponentials — use the FFT for those.

    Args:
        data: Input DataArray
        dim: Dimension name (e.g. time) to transform along
        n_points: Number of log-spaced decay times
        regularization: Tikhonov weight, relative to sqrt(number of samples)
    Returns:
        DataArray with dim replaced by 'decay_time' (same units as dim, name
        stored in attrs['spectrum_dim']), spanning the sample spacing up to
        the measured time window
    Raises:
        ValueError: If dim is not in data.dims or has fewer than 3 points
    """
    if dim not in data.dims:
        raise ValueError(f"Dimension '{dim}' not found in data (has: {list(data.dims)})")
    times = np.asarray(data.coords[dim].values, dtype=float)
    if times.size < 3:
        raise ValueError(f"Dimension '{dim}' has size {times.size}, need at least 3")
    decay_times = decay_time_axis(times, n_points)

    traces = np.moveaxis(np.asarray(data.values, dtype=float), data.get_axis_num(dim), -1)
    flat = traces.reshape(-1, times.size)
    spectra = np.full((flat.shape[0], decay_times.size), np.nan)
    for row, trace in enumerate(flat):
        valid = np.isfinite(trace) & np.isfinite(times)
        if valid.sum() >= 3:
            spectra[row] = _decay_spectrum_1d(
                times[valid], trace[valid], decay_times, regularization)
    spectra = np.moveaxis(
        spectra.reshape(traces.shape[:-1] + (decay_times.size,)),
        -1, data.get_axis_num(dim))

    decay_dim = 'decay_time'
    existing = set(d for d in data.dims if d != dim) | (set(data.coords) - {dim})
    while decay_dim in existing:
        decay_dim = 'decay_' + decay_dim
    new_dims = [d if d != dim else decay_dim for d in data.dims]
    coords = {d: data.coords[d] for d in data.dims if d != dim and d in data.coords}
    coords[decay_dim] = xr.Variable(
        decay_dim, decay_times,
        attrs={'units': data.coords[dim].attrs.get('units', ''), 'long_name': 'decay time'})
    return xr.DataArray(spectra, dims=new_dims, coords=coords,
                        attrs={"spectrum_dim": decay_dim})


def decay_time_axis(times: np.ndarray, n_points: int = DECAY_TIME_POINTS) -> np.ndarray:
    """Log-spaced decay times from the smallest sample spacing to the time window."""
    times = np.sort(np.asarray(times, dtype=float)[np.isfinite(times)])
    spacing = np.diff(times)
    spacing = spacing[spacing > 0]
    if spacing.size == 0:
        raise ValueError("Need at least two distinct time points for a decay spectrum")
    return np.logspace(
        np.log10(spacing.min()), np.log10(times[-1] - times[0]), n_points)


def _decay_spectrum_1d(
    times: np.ndarray, trace: np.ndarray, decay_times: np.ndarray,
    regularization: float,
) -> np.ndarray:
    """Non-negative decay amplitudes of one trace, see `compute_decay_spectrum`."""
    order = np.argsort(times)
    times, trace = times[order], trace[order]
    sign = 1.0 if trace[0] >= trace[-1] else -1.0
    basis = np.exp(-(times - times[0])[:, None] / decay_times[None, :])
    offset = np.ones((times.size, 1))
    n_amplitudes = decay_times.size
    penalty = np.zeros((n_amplitudes, n_amplitudes + 2))
    penalty[:, :n_amplitudes] = regularization * np.sqrt(times.size) * np.eye(n_amplitudes)
    system = np.vstack([np.hstack([basis, offset, -offset]), penalty])
    target = np.concatenate([sign * trace, np.zeros(n_amplitudes)])
    amplitudes, _ = nnls(system, target, maxiter=50 * system.shape[1])
    return amplitudes[:n_amplitudes]


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

    data_np = data.values

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

    # Comparisons with NaN are False, so NaN and ±inf fall out of range
    in_range = (flat_2d >= bin_edges[0]) & (flat_2d <= bin_edges[-1])
    indices = _bin_indices(flat_2d, bin_edges, in_range)

    # Histogram of all rows at once via one bincount. Each row gets n_bins + 1
    # slots; the extra overflow slot collects out-of-range values and is dropped.
    row_offsets = np.arange(n_rows, dtype=np.intp)[:, np.newaxis] * (n_bins + 1)
    hist = np.bincount(
        (indices + row_offsets).ravel(), minlength=n_rows * (n_bins + 1))
    hist = hist.reshape(n_rows, n_bins + 1)[:, :n_bins]

    return hist.reshape(batch_shape + (n_bins,))


def _bin_indices(
    values: np.ndarray, bin_edges: np.ndarray, in_range: np.ndarray
) -> np.ndarray:
    """
    Bin index of each value, matching `np.digitize` semantics: bin i holds
    edges[i] <= v < edges[i+1], the last bin also includes the right edge.
    Values outside `in_range` get the overflow index n_bins.

    Args:
        values: Array of values
        bin_edges: 1D array of increasing bin edges
        in_range: Boolean mask of finite values within [edges[0], edges[-1]]
    Returns:
        Integer array of the same shape with indices in 0..n_bins
    """
    n_bins = len(bin_edges) - 1
    widths = np.diff(bin_edges)
    if not np.allclose(widths, widths[0]):
        indices = np.searchsorted(bin_edges, values, side='right') - 1
        return np.where(in_range, np.minimum(indices, n_bins - 1), n_bins)

    # Uniform bins (the default): arithmetic is much faster than a binary search
    scale = n_bins / (bin_edges[-1] - bin_edges[0])
    with np.errstate(invalid='ignore'):
        position = np.where(in_range, (values - bin_edges[0]) * scale, n_bins)
    indices = position.astype(np.intp)
    np.minimum(indices, n_bins - 1, out=indices, where=in_range)

    # Float rounding can misplace values sitting right at a bin edge; fix those
    fraction = position - indices
    near_edge = in_range & ((fraction < 1e-6) | (fraction > 1 - 1e-6))
    if near_edge.any():
        near_values = values[near_edge]
        near_indices = indices[near_edge]
        near_indices -= near_values < bin_edges[near_indices]
        near_indices += ((near_values >= bin_edges[near_indices + 1])
                         & (near_indices < n_bins - 1))
        indices[near_edge] = near_indices
    return indices
