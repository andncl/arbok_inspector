"""Gaussian fitting analysis using lmfit"""
from typing import TYPE_CHECKING
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from lmfit.models import GaussianModel

from arbok_inspector.analysis.AnalysisBase import AnalysisBase, AnalysisParameter

if TYPE_CHECKING:
    from xarray import Dataset


class FitGaussianAnalysis(AnalysisBase):
    """Fits a Gaussian (via lmfit) per target-state slice, or to the averaged data."""
    name = "Fit Gaussian"

    def provide_analysis_parameters(self, result_vars: list, dim_names: list) -> list[AnalysisParameter]:
        return [
            AnalysisParameter("result_var", "Result variable", result_vars),
            AnalysisParameter("x_axis_dim", "X axis", dim_names),
            AnalysisParameter("target_state_dim", "Target state", ["None"] + dim_names),
        ]

    def run( self, ds: Dataset, params: dict) -> tuple[go.Figure, str]:
        data = ds[params["result_var"]]
        xs = data.coords[params["x_axis_dim"]].values

        if params["target_state_dim"] and params["target_state_dim"] in data.dims:
            state_values = data.coords[params["target_state_dim"]].values
            fig = make_subplots(
                rows=len(state_values), cols=1, shared_xaxes=True,
                subplot_titles=[f"State {int(s)}" for s in state_values],
            )
            summary_lines = []
            for row, state_val in enumerate(state_values, start=1):
                slice_data = data.sel({params["target_state_dim"]: state_val})
                avg_cnts = _average_non_freq(slice_data, params["x_axis_dim"])
                fit_result, fit_curve = _fit_gaussian(xs, avg_cnts)
                fig.add_scatter(
                    x=xs.tolist(), y=avg_cnts.tolist(),
                    mode="lines+markers", name=f"state {int(state_val)}",
                    row=row, col=1,
                )
                fig.add_scatter(
                    x=xs.tolist(), y=fit_curve.tolist(),
                    mode="lines", name=f"fit {int(state_val)}",
                    line=dict(color="orange"), row=row, col=1,
                )
                center = fit_result.params["center"].value
                fwhm = fit_result.params["fwhm"].value
                summary_lines.append(
                    f"State {int(state_val)}: center={center:.6g}, FWHM={fwhm:.6g}"
                )
            fig.update_layout(
                template="plotly_dark",
                xaxis_title=params["x_axis_dim"].replace("__", "."),
            )
            summary = " | ".join(summary_lines)
        else:
            avg_cnts = _average_non_freq(data, params["x_axis_dim"])
            fit_result, fit_curve = _fit_gaussian(xs, avg_cnts)
            fig = go.Figure()
            fig.add_scatter(
                x=xs.tolist(), y=avg_cnts.tolist(),
                mode="lines+markers", name=params["result_var"].replace("__", "."),
            )
            fig.add_scatter(
                x=xs.tolist(), y=fit_curve.tolist(),
                mode="lines", name="Gaussian fit", line=dict(color="orange"),
            )
            fig.update_layout(
                template="plotly_dark",
                xaxis_title=params["x_axis_dim"].replace("__", "."),
                yaxis_title=f"avg {params["result_var"].replace('__', '.')}",
            )
            center = fit_result.params["center"].value
            fwhm = fit_result.params["fwhm"].value
            summary = f"center={center:.6g}, FWHM={fwhm:.6g}"

        return fig, summary


def _average_non_freq(data, freq_dim: str) -> np.ndarray:
    avg_axes = tuple(i for i, d in enumerate(data.dims) if d != freq_dim)
    return np.nanmean(data.values, axis=avg_axes) if avg_axes else data.values.copy()


def _fit_gaussian(freqs: np.ndarray, counts: np.ndarray) -> tuple:
    model = GaussianModel()
    peak_idx = int(np.argmax(counts))
    sigma_guess = (freqs[-1] - freqs[0]) / 20
    params = model.make_params(
        center=freqs[peak_idx],
        amplitude=counts[peak_idx] * sigma_guess * np.sqrt(2 * np.pi),
        sigma=sigma_guess,
    )
    result = model.fit(counts, params, x=freqs)
    return result, result.best_fit