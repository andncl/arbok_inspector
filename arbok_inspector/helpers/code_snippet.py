"""Python code that reproduces the current run view in a notebook."""
from __future__ import annotations
from typing import TYPE_CHECKING

from pathlib import Path

if TYPE_CHECKING:
    from arbok_inspector.classes.base_run import BaseRun
    from arbok_inspector.classes.view_state import ViewState


def python_snippet(run: BaseRun, view: ViewState) -> str:
    """
    Code computing exactly the plotted data of `view`, in the same order as
    `BaseRun.compute_subset`: average (or bin) → FFT / decay → range → select.
    The result is a dict `data` of xarray DataArrays, one per plotted result.
    """
    dataset = run.full_data_set
    names = [n for n in view.plot_selection if n in dataset.data_vars]
    avg_dims = [run.resolve_dim(d) for d in view.avg_dims]
    selection = {}
    for name, index in view.selection:
        dim = run.resolve_dim(name)
        selection[dim] = min(index, dataset.sizes[dim] - 1) if dim in dataset.sizes else index

    imports = []
    steps = []
    if view.fft_dim is not None:
        imports.append("compute_fft")
        if avg_dims:
            steps.append(f"arr = arr.mean({avg_dims!r})")
        steps.append(
            f"arr = compute_fft(arr, dim={run.resolve_dim(view.fft_dim)!r}, "
            f"representation={view.fft_representation!r})")
        steps += _range_step(view.fft_freq_range)
    elif view.decay_dim is not None:
        imports.append("compute_decay_spectrum")
        if avg_dims:
            steps.append(f"arr = arr.mean({avg_dims!r})")
        steps.append(
            f"arr = compute_decay_spectrum(arr, dim={run.resolve_dim(view.decay_dim)!r})")
        steps += _range_step(view.decay_range)
    elif view.show_histogram:
        imports.append("bin_over_axis")
        steps.append(f"arr = bin_over_axis(arr, dim={avg_dims!r})")
    elif avg_dims:
        steps.append(f"arr = arr.mean({avg_dims!r})")
    if selection:
        steps.append(f"arr = arr.isel({selection!r}).squeeze()")

    lines = []
    if hasattr(run, "db_path"):
        lines.append("from qcodes.dataset import initialise_or_create_database_at, load_by_id")
    if imports:
        lines.append(
            f"from arbok_inspector.analysis.prepare_data import {', '.join(imports)}")
    lines.append("")
    if hasattr(run, "db_path"):
        lines.append(f"initialise_or_create_database_at({str(Path(run.db_path).resolve())!r})")
        lines.append(
            f"ds = load_by_id({run.run_id}).to_xarray_dataset(use_multi_index='never')")
    else:
        lines.append(f"ds = ...  # xarray Dataset of run {run.run_id}")
    lines.append("")
    lines.append("data = {}")
    lines.append(f"for name in {names!r}:")
    lines.append("    arr = ds[name]")
    lines += [f"    {step}" for step in steps]
    lines.append("    data[name] = arr")
    axes = [f"{label} = {value}" for label, value in
            (("x", view.x_dim), ("y", view.y_dim)) if value is not None]
    if axes:
        lines.append(f"# plotted with {', '.join(axes)}")
    return "\n".join(lines) + "\n"


def _range_step(index_range: tuple[int, int] | None) -> list[str]:
    if index_range is None:
        return []
    lo, hi = index_range
    return [f"arr = arr.isel({{arr.attrs['spectrum_dim']: slice({lo}, {hi + 1})}})"]
