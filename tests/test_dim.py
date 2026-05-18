"""Tests for the Dim data class."""
from arbok_inspector.classes.dim import Dim, AXIS_OPTIONS


def test_dim_creation():
    dim = Dim("frequency")
    assert dim.name == "frequency"
    assert dim.option is None
    assert dim.select_index == 0


def test_dim_str_repr():
    dim = Dim("voltage")
    assert str(dim) == "voltage"
    assert "voltage" in repr(dim)


def test_dim_option_assignment():
    dim = Dim("iteration")
    dim.option = "average"
    dim.select_index = 5
    assert dim.option == "average"
    assert dim.select_index == 5


def test_axis_options_available():
    assert "average" in AXIS_OPTIONS
    assert "select_value" in AXIS_OPTIONS
    assert "x-axis" in AXIS_OPTIONS
    assert "y-axis" in AXIS_OPTIONS
