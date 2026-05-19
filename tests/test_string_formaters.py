"""Tests for helpers/string_formaters.py"""
import numpy as np
import xarray as xr
import pytest

from arbok_inspector.helpers.string_formaters import axis_label_formater, title_formater


class TestAxisLabelFormater:
    def make_array(self, dim_name, units=None):
        coords = {dim_name: np.arange(5, dtype=float)}
        arr = xr.DataArray(np.zeros(5), dims=[dim_name], coords=coords)
        if units is not None:
            arr.coords[dim_name].attrs["units"] = units
        return arr

    def test_single_part_with_units(self):
        arr = self.make_array("voltage", units="V")
        result = axis_label_formater(arr, "voltage")
        assert "<b>voltage</b>" in result
        assert "(V)" in result

    def test_double_underscore_split(self):
        arr = xr.DataArray(
            np.zeros(5),
            dims=["qubit__frequency"],
            coords={"qubit__frequency": np.arange(5, dtype=float)},
        )
        arr.coords["qubit__frequency"].attrs["units"] = "Hz"
        result = axis_label_formater(arr, "qubit__frequency")
        assert "qubit.<b>frequency</b>" in result
        assert "(Hz)" in result

    def test_no_units_attr(self):
        arr = self.make_array("time")
        result = axis_label_formater(arr, "time")
        assert "<b>time</b>" in result
        assert "()" in result

    def test_multi_level_namespace(self):
        dim = "device__qubit__frequency"
        arr = xr.DataArray(
            np.zeros(3),
            dims=[dim],
            coords={dim: np.arange(3, dtype=float)},
        )
        arr.coords[dim].attrs["units"] = "GHz"
        result = axis_label_formater(arr, dim)
        assert "device.qubit.<b>frequency</b>" in result


class TestTitleFormater:
    def test_empty_select_value(self):
        class FakeRun:
            dim_axis_option = {"select_value": []}
            full_data_set = xr.Dataset()
        result = title_formater(FakeRun())
        assert result == ""

    def test_formats_selected_dims(self):
        class FakeDim:
            def __init__(self, name, select_index):
                self.name = name
                self.select_index = select_index

        voltage = np.linspace(0, 1, 5)
        ds = xr.Dataset(
            {"data": (["voltage"], np.zeros(5))},
            coords={"voltage": voltage},
        )
        ds["voltage"].attrs["units"] = "V"

        class FakeRun:
            dim_axis_option = {"select_value": [FakeDim("voltage", 2)]}
            full_data_set = ds

        result = title_formater(FakeRun())
        assert "voltage" in result
        assert "=" in result
