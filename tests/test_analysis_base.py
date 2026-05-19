"""Tests for analysis/analysis_base.py"""
import numpy as np
import xarray as xr
import pytest

from arbok_inspector.analysis.analysis_base import AnalysisBase


class TestAnalysisBase:
    def make_analysis(self):
        ab = AnalysisBase()
        ab.xr_data = xr.DataArray(
            np.zeros((3, 4, 5)),
            dims=["voltage", "frequency", "iteration"],
        )
        return ab

    def test_find_axis_exact_keyword(self):
        ab = self.make_analysis()
        assert ab.find_axis_from_keyword("voltage") == "voltage"

    def test_find_axis_partial_keyword(self):
        ab = self.make_analysis()
        assert ab.find_axis_from_keyword("freq") == "frequency"

    def test_find_axis_no_match_raises(self):
        ab = self.make_analysis()
        with pytest.raises(ValueError, match="not found"):
            ab.find_axis_from_keyword("nonexistent")

    def test_find_axis_multiple_matches_raises(self):
        ab = AnalysisBase()
        ab.xr_data = xr.DataArray(
            np.zeros((3, 4)),
            dims=["iter_fast", "iter_slow"],
        )
        with pytest.raises(ValueError, match="More than one"):
            ab.find_axis_from_keyword("iter")
