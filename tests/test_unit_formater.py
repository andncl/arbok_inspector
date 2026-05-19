"""Tests for helpers/unit_formater.py"""
import numpy as np
import xarray as xr
import pytest

from arbok_inspector.helpers.unit_formater import unit_formatter


class FakeDim:
    def __init__(self, name, select_index=0):
        self.name = name
        self.select_index = select_index


class FakeRun:
    def __init__(self, dataset):
        self.full_data_set = dataset


def make_run(values, units=None):
    """Helper to create a FakeRun with a 'coord' variable."""
    ds = xr.Dataset(
        {"data": (["coord"], np.zeros(len(values)))},
        coords={"coord": values},
    )
    if units is not None:
        ds["coord"].attrs["units"] = units
    return FakeRun(ds)


class TestUnitFormatter:
    def test_giga_prefix(self):
        run = make_run([5e9], units="Hz")
        result = unit_formatter(run, FakeDim("coord"), 0)
        assert "5" in result
        assert "G" in result
        assert "Hz" in result

    def test_mega_prefix(self):
        run = make_run([1.2e6], units="Hz")
        result = unit_formatter(run, FakeDim("coord"), 0)
        assert "1.2" in result
        assert "M" in result

    def test_kilo_prefix(self):
        run = make_run([1532.0], units="V")
        result = unit_formatter(run, FakeDim("coord"), 0)
        assert "1.53" in result
        assert "k" in result

    def test_milli_prefix(self):
        run = make_run([0.005], units="V")
        result = unit_formatter(run, FakeDim("coord"), 0)
        assert "5" in result
        assert "m" in result

    def test_micro_prefix(self):
        run = make_run([0.00042], units="s")
        result = unit_formatter(run, FakeDim("coord"), 0)
        assert "420" in result
        assert "µ" in result

    def test_nano_prefix(self):
        run = make_run([0.0000008], units="s")
        result = unit_formatter(run, FakeDim("coord"), 0)
        assert "800" in result
        assert "n" in result

    def test_zero_value(self):
        run = make_run([0.0], units="V")
        result = unit_formatter(run, FakeDim("coord"), 0)
        assert "0" in result

    def test_no_unit_returns_raw_value(self):
        run = make_run([42.0], units="")
        result = unit_formatter(run, FakeDim("coord"), 0)
        assert "42" in result
        assert "k" not in result

    def test_missing_dim_returns_na(self):
        run = make_run([1.0], units="V")
        result = unit_formatter(run, FakeDim("nonexistent"), 0)
        assert "N/A" in result

    def test_index_out_of_range_returns_na(self):
        run = make_run([1.0], units="V")
        result = unit_formatter(run, FakeDim("coord"), 99)
        assert "N/A" in result

    def test_no_units_attr(self):
        """Coordinate without 'units' attribute should return N/A."""
        run = make_run([5.0])
        result = unit_formatter(run, FakeDim("coord"), 0)
        assert "N/A" in result

    def test_value_between_1_and_1000_no_prefix(self):
        run = make_run([42.0], units="V")
        result = unit_formatter(run, FakeDim("coord"), 0)
        assert "42" in result
        assert "k" not in result
        assert "m" not in result
