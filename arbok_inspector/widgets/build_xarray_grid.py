"""Plot grid of a run view: renders the selected results as Plotly figures."""
from __future__ import annotations
from typing import TYPE_CHECKING, Callable

import asyncio
import itertools
import logging
import math
from pathlib import Path

from nicegui import ui
from nicegui import run as nicegui_run

from arbok_inspector.helpers.figure_builder import (
    DEFAULT_FONT_SIZE, PlotSettings, FigureBundle, build_figures
)
from arbok_inspector.helpers.render_scheduler import RenderScheduler
from arbok_inspector.helpers.string_formaters import title_formater
from arbok_inspector.run_session import get_session

if TYPE_CHECKING:
    from arbok_inspector.classes.base_run import BaseRun
    from arbok_inspector.classes.view_state import ViewState
    from arbok_inspector.run_session import RunSession

logger = logging.getLogger(__name__)

SPINNER_DELAY_S = 0.3


def compute_figures(
        run: BaseRun, view: ViewState, settings: PlotSettings) -> FigureBundle:
    """Heavy part of a render: subset the data and build the figure dicts."""
    data = run.compute_subset(view)
    return build_figures(data, view, settings)


class PlotGrid:
    """
    Plot area of one run-view tab.

    A render is split in two: the heavy part (`compute_figures`) runs in a
    worker thread, so the event loop shared by all tabs stays responsive; only
    applying the result to the UI runs on the loop. Renders go through a
    RenderScheduler — one at a time, the latest request wins — and existing
    plots are updated in place while the grid layout stays the same.
    """

    def __init__(
            self, session: RunSession,
            on_reloaded: Callable[[], None] | None = None):
        """
        Args:
            session: Session of the tab this grid belongs to
            on_reloaded: Called on the event loop after the dataset was reloaded
        """
        self.session = session
        self.on_reloaded = on_reloaded
        self._plots: list[ui.plotly] = []
        self._layout_key: tuple[int, int] | None = None
        self._scheduler = RenderScheduler(self._render)
        with ui.element('div').classes('relative w-full') as self._root:
            self._area = ui.row().classes('w-full min-h-[50vh] p-1 items-stretch')
            self._spinner = ui.spinner('dots', size='lg', color='purple')\
                .classes('absolute top-2 right-2 z-10')
            self._spinner.visible = False

    @property
    def busy(self) -> bool:
        """True while a render is running or queued."""
        return self._scheduler.busy

    def request(self, reload: bool = False) -> None:
        """Request a render without waiting for it (see RenderScheduler)."""
        self._scheduler.request(reload)

    async def refresh(self, reload: bool = False) -> None:
        """Request a render and wait until the plots are up to date."""
        self.request(reload)
        await self._scheduler.wait_idle()

    async def wait_idle(self) -> None:
        """Wait until all requested renders have finished."""
        await self._scheduler.wait_idle()

    def close(self) -> None:
        """Cancel pending renders, e.g. when the tab is closed."""
        self._scheduler.close()

    async def _render(self, reload: bool) -> None:
        if self._root.is_deleted:
            return
        show_spinner = asyncio.get_running_loop().call_later(
            SPINNER_DELAY_S, self._set_spinner, True)
        try:
            with self._root:
                await self._render_in_context(reload)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("Plot render failed")
            if not self._root.is_deleted:
                with self._root:
                    ui.notify(f'Error while plotting: {e}', type='negative')
        finally:
            show_spinner.cancel()
            self._set_spinner(False)

    async def _render_in_context(self, reload: bool) -> None:
        run = self.session.run
        if reload:
            await nicegui_run.io_bound(run.reload_dataset)
            if self._root.is_deleted:
                return
            if self.on_reloaded is not None:
                self.on_reloaded()
        view = run.snapshot_view()
        if (view.x_dim is None and not view.show_histogram
                and view.fft_dim is None and view.decay_dim is None):
            self._clear()
            ui.notify(
                'Please select at least one dimension for the x-axis to display plots.',
                color='red')
            return
        settings = self._snapshot_settings()
        bundle = await nicegui_run.io_bound(compute_figures, run, view, settings)
        if bundle is None or self._root.is_deleted:
            return  # app is shutting down or tab was closed meanwhile
        self._apply(bundle)

    def _snapshot_settings(self) -> PlotSettings:
        """Capture the tab's plot settings and title texts on the event loop."""
        run = self.session.run
        settings = self.session.settings
        title_header = ""
        if hasattr(run, 'db_path'):
            title_header = (f"Run ID: {run.run_id} -- "
                            f"<i>{Path(run.db_path).resolve()}</i><br>")
        return PlotSettings(
            plot_dict_1d=settings["plot_dict_1D"],
            plot_dict_2d=settings["plot_dict_2D"],
            font_size=settings.get("plot_font_size", DEFAULT_FONT_SIZE),
            log_x=settings.get("log_scale_x", False),
            log_y=settings.get("log_scale_y", False),
            log_z=settings.get("log_scale_z", False),
            show_gridlines=settings.get("show_gridlines", True),
            title_header=title_header,
            title_selection=title_formater(run),
            show_ridge=settings.get("show_ridge", False),
            z_range_mode=settings.get("z_range_mode", "auto"),
            z_min=settings.get("z_min"),
            z_max=settings.get("z_max"),
            export_format=settings.get("export_format", "svg"),
            export_filename=f"run{run.run_id}",
        )

    def _apply(self, bundle: FigureBundle) -> None:
        """Show the computed figures, reusing existing plot elements if possible."""
        for warning in bundle.warnings:
            ui.notify(warning, type='negative')
        if bundle.last_figure_1d is not None:
            self.session.settings["last_figure_1d"] = bundle.last_figure_1d
        if bundle.last_figure_2d is not None:
            self.session.settings["last_figure_2d"] = bundle.last_figure_2d
        figures = bundle.figures
        if not figures:
            self._clear()
            with self._area:
                ui.label('No plottable results selected').classes('text-gray-400')
            return
        layout_key = (len(figures), max(1, self.session.run.plots_per_column))
        if layout_key == self._layout_key and not any(p.is_deleted for p in self._plots):
            for plot, figure in zip(self._plots, figures):
                plot.update_figure(figure)
            return
        self._build_grid(figures, num_columns=min(layout_key[1], len(figures)))
        self._layout_key = layout_key

    def _build_grid(self, figures: list[dict], num_columns: int) -> None:
        """Create a grid of plotly elements, `num_columns` per row."""
        self._clear()
        num_rows = math.ceil(len(figures) / num_columns)
        width_percent = 100 / num_columns - 2
        height_percent = 100 / num_rows - 2
        remaining = iter(figures)
        with self._area, ui.column().classes('w-full h-full'):
            for _ in range(num_rows):
                with ui.row().classes('w-full justify-start flex-wrap'):
                    for figure in itertools.islice(remaining, num_columns):
                        with ui.column().style(
                                f"width: {width_percent}%; box-sizing: border-box;"
                                f"height: {height_percent}%; box-sizing: border-box;"):
                            plot = ui.plotly(figure).classes('w-full h-full')\
                                .style(f'min-height: {int(800/num_rows)}px;')
                            self._plots.append(plot)

    def _clear(self) -> None:
        self._area.clear()
        self._plots = []
        self._layout_key = None

    def _set_spinner(self, visible: bool) -> None:
        if not self._spinner.is_deleted:
            self._spinner.set_visibility(visible)


def request_plot_update(reload: bool = False) -> None:
    """
    Request a re-render of the current tab's plots. Returns immediately;
    bursts of requests are coalesced into one render with the latest state.

    Args:
        reload: Whether to reload the dataset from the database first.
    """
    session = get_session()
    if session is None or session.plot_grid is None:
        ui.notify('Session expired — please reload the page.', type='warning')
        return
    session.plot_grid.request(reload)
