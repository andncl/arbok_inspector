"""Module containing prepare_data function for analysis tools"""

from matplotlib.pylab import f
from qcodes.dataset.data_set import load_by_id, DataSet
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt

def prepare_and_avg_data(
    run: int | DataSet | xr.Dataset | xr.DataArray,
    readout_name: str,
    avg_axes: str | list = 'auto'
    ) -> tuple[int | None, xr.DataArray, np.ndarray]:
    """
    Prepares the data for plotting. Takes either a run id, a qcodes dataset,
    an xarray dataset or an xarray data-array and returns the run id, the xarray
    data-array and the numpy data-array.
    This is done to allow different input types for the data while keeping the
    same output format.
    
    Args:
        run (int | DataSet | xr.Dataset | xr.DataArray): Run id, qcodes dataset'
            xarray dataset or xarray data-array
        readout_name (str): Name of the readout observable
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
        run_id = xdataset.attrs['run_id']
    elif isinstance(run, xr.DataArray):
        xdataset = None
        xdata_array = run
        run_id = None
    else:
        raise ValueError(
            "Invalid input type for run. "
            "Must be run-ID, DataSet or xr.Dataset or xr.DataArray. "
            f"Is {type(run)}"
            )
    if xdataset is not None:
        if readout_name not in xdataset.data_vars:
            readout_name = find_data_variable_from_keyword(xdataset, readout_name)
        xdata_array = xdataset[readout_name]
    ### Average over specified axes
    xdata_array = avg_dataarray(xdata_array, avg_axes)
    np_data = xdata_array.to_numpy()
    return run_id, xdata_array, np_data

def find_data_variable_from_keyword(
        xdata_array: xr.DataArray, keyword: str | tuple) -> str:
    """
    Find the data variable corresponding to a keyword in the data-array.
    
    Args:
        xdata_array (xr.DataArray): xarray data-array to search in
        keyword (str): Keyword to search for
    Returns:
        data_variable (str): Data variable corresponding to keyword
    """
    if isinstance(keyword, str):
        keyword = (keyword,)
    if not isinstance(keyword, tuple):
        raise ValueError(
            f"Keyword must be a string or a tuple. Is {type(keyword)}")
    data_variables = []
    for data_variable in xdata_array.data_vars:
        if all([subkey in str(data_variable) for subkey in keyword]):
            data_variables.append(data_variable)
    if len(data_variables) == 0:
        raise ValueError(
            f"Data variable not found for keyword {keyword}. "
            f"Data variables are {xdata_array.data_vars}"
            )
    elif len(data_variables) > 1:
        raise ValueError(
            f"More than one data variable found for keyword {keyword}: "
            f"{[str(var) for var in data_variables]}")
    else:
        return data_variables[0]

def avg_dataarray(xdata_array: xr.DataArray, avg_axes: str | list = 'auto'):
    """
    Averages the data-array over the specified axes. If no axes are specified
    the data-array is averaged over all axes.
    
    Args:
        xdata_array (xr.DataArray): xarray data-array to be averaged
        avg_axes (str | list): Axes to average over
    """
    if avg_axes is None:
        avg_axes = []
    if isinstance(avg_axes, str):
        ### If 'auto' is given, find all axes with 'iteration' in the name
        if avg_axes == 'auto':
            avg_axes = []
            for dim in xdata_array.dims:
                if 'iteration' in dim:
                    avg_axes.append(dim)
        else:
            avg_axes = [avg_axes]
    ### Average over specified axes
    for axis in avg_axes:
        if hasattr(xdata_array, axis):
            xdata_array = xdata_array.mean(axis)
        else:
            raise KeyError(
                f"Avg. axis {axis} not found in xarray data-array")
    return xdata_array
