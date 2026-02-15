"""Find peaks analysis using scipy.signal.find_peaks"""
from typing import TYPE_CHECKING
import numpy as np
import plotly.graph_objects as go
from scipy.signal import find_peaks

from arbok_inspector.analysis.AnalysisBase import AnalysisBase, AnalysisParameter

if TYPE_CHECKING:
    from xarray import Dataset


class FindPeaksAnalysis(AnalysisBase):
    """Averages over all non-frequency dims and finds peaks with scipy."""
    name = "Find Peaks"

    def provide_analysis_parameters(self, result_vars: list, dim_names: list) -> list[AnalysisParameter]:
        return [
            AnalysisParameter("result_var", "Result variable", result_vars),
            AnalysisParameter("freq_dim", "Frequency axis", dim_names),
        ]

    def run(self, ds: Dataset, params: dict) -> tuple[go.Figure, str]:
        # TODO: Move to params
        rel_height = 0.8

        data = ds[params["result_var"]]
        freqs = data.coords[params["freq_dim"]].values
        avg_axes = tuple(i for i, d in enumerate(data.dims) if d != params["freq_dim"])
        avg_cnts = np.nanmean(data.values, axis=avg_axes) if avg_axes else data.values

        peak_indices, _ = find_peaks(
            avg_cnts,
            distance=max(1, len(freqs) // 20),
            width=1,
            height=np.nanmax(avg_cnts) / rel_height,
        )
        print(peak_indices)

        fig = go.Figure()
        fig.add_scatter(
            x=freqs.tolist(), y=avg_cnts.tolist(),
            mode="lines+markers", name=params["result_var"].replace("__", ".")
        )
        fig.add_scatter(
            x=freqs[peak_indices].tolist(), y=avg_cnts[peak_indices].tolist(),
            mode="markers",
            marker=dict(symbol="square", color="orange", size=10),
            name="peaks",
        )
        fig.update_layout(
            template="plotly_dark",
            xaxis_title=params["freq_dim"].replace("__", "."),
            yaxis_title=f"avg {params["result_var"].replace('__', '.')}",
        )
        return fig, f"Peaks at: {[round(float(f), 6) for f in freqs[peak_indices]]}"