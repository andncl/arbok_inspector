"""
Base analysis class.

Custom analysis classes should implement appropriate methods
"""
from typing import TYPE_CHECKING

import plotly.graph_objs as go

if TYPE_CHECKING:
    from xarray import Dataset


class AnalysisParameter:
    """Analysis parameter"""
    def __init__(self, label: str, name: str, value: list | str | float):
        self.label = label  # Internal eg "result_var"
        self.name = name    # Pretty eg "Result variable"
        self.value = value  # result_vars selection. If a list, the default value is the first value


class AnalysisBase:
    """Base class for analysis classes"""
    name = ""

    def provide_analysis_parameters(self, result_vars: list, dim_names: list) -> list[AnalysisParameter]:
        """Provide the needed dimension selection. Either a dimension or """
        # TODO: Add optional support for different types. Eg float so that other parameters can be specified by the analysis framework
        # Probably something like the following:
        # return [
        #     AnalysisParameter("result_var", "Result variable", dim_names),
        #     AnalysisParameter("freq_dim", "Frequency axis", dim_names),
        # ]
        raise NotImplementedError


    def run(self, ds: Dataset, params: dict) -> tuple[go.Figure, str]:
        """Run the analysis function on the given dataset"""
        return go.Figure(), ""




