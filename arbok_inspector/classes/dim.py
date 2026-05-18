"""Module for the Dim class representing a data dimension."""
from __future__ import annotations


AXIS_OPTIONS = ['average', 'select_value', 'y-axis', 'x-axis']


class Dim:
    """Pure data class representing a dimension and its current role in plotting."""

    def __init__(self, name: str):
        self.name: str = name
        self.option: str | None = None
        self.select_index: int = 0

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"Dim(name={self.name!r}, option={self.option!r}, select_index={self.select_index})"
