"""Helper functions for formatting units with SI prefixes."""

def unit_formatter(run, dim, index: int) -> str:
    """
    If value is larger than 1e3, format with SI prefix.
    Same if smaller than 1e-3.

    Args:
        run (Run): Run object containing the data
        dim (Dim): Dimension object
        index (int): Index of the value to format
    """
    unit_tuples = [
        ('G', 1e9), ('M', 1e6), ('k', 1e3), ('m', 1e-3), ('µ', 1e-6), ('n', 1e-9)]
    try:
        value = run.full_data_set[dim.name].values[index]
        unit = run.full_data_set[dim.name].attrs['units']
        if abs(value) >= 1e3 or (abs(value) < 1e-3 and value != 0):
            for prefix, factor in unit_tuples:
                if abs(value) >= factor or (abs(value) < 1e-3 and value != 0 and factor < 1):
                    scaled_value = value / factor
                    return f'{scaled_value:.3f} {prefix}<b>{unit}</b>'
        if unit is None or unit == '':
            return f'{value:.3f}'
        else:
            return f'{value:.3f} ({unit})'
    except Exception as e:
        print(f"Error in unit_formatter: {e}")
        return 'N/A'