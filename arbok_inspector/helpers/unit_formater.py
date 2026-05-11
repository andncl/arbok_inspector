"""Helper functions for formatting units with SI prefixes."""

def unit_formatter(run, dim, index: int) -> str:
    """
    Format a numeric value into an HTML string using SI prefixes,
    keeping at most 3 significant digits.

    Examples:
        1532      -> "1.53 k"
        1200000   -> "1.2 M"
        0.00042   -> "420 µ"
        0.0000008 -> "800 n"
    """
    unit_tuples = [
        ('G', 1e9), ('M', 1e6), ('k', 1e3), ('m', 1e-3), ('µ', 1e-6), ('n', 1e-9)]

    try:
        value = run.full_data_set[dim.name].values[index]
        unit = run.full_data_set[dim.name].attrs['units']
        unit = unit if unit is not None else ''
    except (KeyError, IndexError):
        return "<span>N/A</span>"

    if value == 0:
        return f"<span>0 ({unit})</span>"
    if unit == '':
        return f"<span>{value}</span>"

    # Default: no prefix
    prefix = ''
    scaled = value

    # Choose best unit
    for p, factor in unit_tuples:
        scaled_candidate = value / factor

        if 1 <= abs(scaled_candidate) < 1000:
            prefix = p
            scaled = scaled_candidate
            break

    # Format to at most 3 significant digits
    if abs(scaled) >= 100:
        formatted = f"{scaled:.0f}"
    elif abs(scaled) >= 10:
        formatted = f"{scaled:.1f}".rstrip('0').rstrip('.')
    else:
        formatted = f"{scaled:.2f}".rstrip('0').rstrip('.')

    return f"<span>{formatted} ({prefix}<b>{unit}</b>)</span>"