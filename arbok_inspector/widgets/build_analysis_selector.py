"""Build and display the different analysis options to apply to the dataset"""
from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

from nicegui import ui, app

from arbok_inspector.analysis.find_peaks_analysis import FindPeaksAnalysis
from arbok_inspector.analysis.fit_gaussian_analysis import FitGaussianAnalysis
# from arbok_inspector.analysis.fit_function_analysis import FitFunctionAnalysis, FIT_FUNCTIONS

if TYPE_CHECKING:
    from arbok_inspector.classes.base_run import BaseRun
    from xarray import Dataset

ANALYSES = {
    "Find Peaks": FindPeaksAnalysis(),
    "Fit Gaussian": FitGaussianAnalysis(),
    # "Fit Function": FitFunctionAnalysis(),
}


def build_analysis_selector():
    """Display the analysis selector"""
    run: BaseRun = app.storage.tab["run"]
    ds: Dataset = run.full_data_set
    result_vars = list(ds.data_vars)
    dim_names = list(ds.dims)

    state = {
        "analysis": "Find Peaks",
        "plot_container": None,
    }

    with ui.column().classes("w-full gap-2 p-2"):
        controls_row = ui.row().classes("items-center gap-2 flex-wrap w-full")
        _build_controls(controls_row, state, result_vars, dim_names)
        state["plot_container"] = ui.row().classes("w-full")


def _build_controls(container, state, result_vars, dim_names):
    container.clear()
    analysis_name = state["analysis"]

    with container:
        def on_analysis_change(e):
            state.update({"analysis": e.value})
            _build_controls(container, state, result_vars, dim_names)

        ui.select(
            options=list(ANALYSES.keys()),
            value=analysis_name,
            label="Analysis",
            on_change=on_analysis_change,
        ).classes("w-40")

        # Based on chosen analysis, provide different sub-selections
        for param in ANALYSES[analysis_name].provide_analysis_parameters(result_vars, dim_names):
            if param.label not in state.keys():
                state[param.label] = param.value[0] if len(param.value) > 0 else param.value  # Inject
            if isinstance(param.value, list):
                ui.select(
                    options=param.value, value=state[param.label], label=param.name,
                    on_change=lambda e: state.update({param.label: e.value}),
                ).classes("w-64")
            # elif isinstance(param.value, str):
            #     ui.input(
            #         label="Expression (use x)", value=state["custom_expr"],
            #         on_change=lambda e: state.update({"custom_expr": e.value}),
            #     ).classes("w-80 font-mono text-sm")
            # elif isinstance(param.value, float):
            #     ...
            else:
                ui.notify("Unsupported type of parameter: " + str(type(param.value)), type="negative")

        ui.button(
            "Run", icon="play_arrow", on_click=lambda: _run_analysis(state),
        ).props("color=purple")


def _run_analysis(state: dict):
    run: BaseRun = app.storage.tab["run"]
    ds: Dataset = run.full_data_set
    container = state["plot_container"]
    container.clear()
    try:
        analysis = ANALYSES[state["analysis"]]
        fig, summary = analysis.run(ds, state)
        with container:
            ui.plotly(fig).classes("w-full").style("min-height: 400px;")
            ui.label(summary).classes("text-sm font-mono")
    except Exception as e:
        print(e)
        traceback.print_exc()
        ui.notify(str(e), type="negative")