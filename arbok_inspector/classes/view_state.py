"""Module for the ViewState class: an immutable snapshot of plot settings."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ViewState:
    """
    Snapshot of everything that determines which data of a run is plotted.

    Taken on the event loop right before a render, so the worker thread that
    computes the plots never sees the UI mutate dims mid-computation.
    """
    avg_dims: tuple[str, ...]
    x_dim: str | None
    y_dim: str | None
    fft_dim: str | None
    selection: tuple[tuple[str, int], ...]
    plot_selection: tuple[str, ...]
    show_histogram: bool = False
    fft_representation: str = 'PSD'
    fft_freq_range: tuple[int, int] | None = None
    decay_dim: str | None = None
    decay_range: tuple[int, int] | None = None
