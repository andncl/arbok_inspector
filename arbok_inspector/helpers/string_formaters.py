
import xarray as xr
from arbok_inspector.helpers.unit_formater import unit_formatter

def title_formater(run, result_name: str | None):
    """
    Format title string for plots based on selected dimensions.
    
    Args:
        run: The Run object containing the data.
        result_name: The name of the result dimension.
    Returns:
        A formatted title string.
    """
    title = ""
    if  result_name is not None:
        for dim in run.result_axes[result_name]["select_value"]:
            title += f"{dim.name.replace('__', '.')} = "
            title += f"{unit_formatter(run, dim, dim.select_index)}<br>"
    return title

def axis_label_formater(ds: xr.DataArray, dim_name: str) -> str:
    """
    Format axis label by replacing '__' with '.' and bolding the last part.
    
    Args:
        dim_name: The dimension name string.
    Returns:
        A formatted axis label string.
    """
    dim_list = dim_name.split('__')
    if 'units' in ds.coords[dim_name].attrs:
        unit = ds.coords[dim_name].attrs['units']
    else:
        unit = ""
    if len(dim_list) > 1:
        return f"{'.'.join(dim_list[:-1])}.<b>{dim_list[-1]}</b> ({unit})"
    else:
        return f"<b>{dim_list[0]}</b> ({unit})"
