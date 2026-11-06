"""Ridge readout: position of the brightest point of FFT / decay spectra."""
from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr


def spectrum_dim_of(data: xr.DataArray) -> str | None:
    """Spectrum dimension (FFT frequency / decay time) of a transformed result."""
    dim = data.attrs.get("spectrum_dim")
    return dim if dim in data.dims else None


def ridge_line(data: xr.DataArray, dim: str) -> xr.DataArray:
    """
    Coordinate of the maximum along `dim`, for every index of the other dims.

    E.g. for a decay spectrum over (voltage, decay_time) this is the dominant
    decay time per voltage. All-NaN rows give NaN.

    Args:
        data: Spectrum, e.g. from `compute_fft` or `compute_decay_spectrum`
        dim: Dimension to take the maximum along
    Returns:
        DataArray over the remaining dims, with the units of `dim`
    """
    values = np.asarray(data.values, dtype=float)
    axis = data.get_axis_num(dim)
    finite = np.isfinite(values)
    index = np.argmax(np.where(finite, values, -np.inf), axis=axis)
    positions = np.asarray(data.coords[dim].values, dtype=float)[index]
    ridge = np.where(finite.any(axis=axis), positions, np.nan)
    kept = [d for d in data.dims if d != dim]
    return xr.DataArray(
        ridge, dims=kept,
        coords={d: data.coords[d] for d in kept if d in data.coords},
        attrs={"units": data.coords[dim].attrs.get("units", "")})


def ridge_csv(results: dict[str, xr.DataArray]) -> str | None:
    """
    CSV with the ridge line of every transformed result, one column each.

    Args:
        results: Plotted results, e.g. `run.last_subset`
    Returns:
        CSV text, or None if no result has a spectrum dimension
    """
    columns = {}
    for name, data in results.items():
        dim = spectrum_dim_of(data)
        if dim is None:
            continue
        ridge = ridge_line(data, dim)
        unit = ridge.attrs["units"]
        label = f"{name.replace('__', '.')} peak {dim}" + (f" ({unit})" if unit else "")
        columns[label] = ridge
    if not columns:
        return None
    if all(ridge.ndim == 0 for ridge in columns.values()):
        frame = pd.DataFrame({label: [float(r)] for label, r in columns.items()})
        return frame.to_csv(index=False)
    lines = {label: r for label, r in columns.items() if r.ndim > 0}
    return xr.Dataset(lines).to_dataframe().to_csv()
