"""UI binding layer for Dim objects. Owns all NiceGUI widget references."""
from __future__ import annotations
from typing import TYPE_CHECKING

from nicegui import ui

from arbok_inspector.classes.dim import Dim, AXIS_OPTIONS
from arbok_inspector.helpers.unit_formater import unit_formatter

if TYPE_CHECKING:
    from nicegui.elements.html import Html
    from nicegui.elements.select import Select
    from nicegui.elements.slider import Slider
    from arbok_inspector.classes.base_run import BaseRun


class DimWidget:
    """Binds a Dim to its NiceGUI UI elements."""

    def __init__(self, dim: Dim):
        self.dim = dim
        self.selector: Select | None = None
        self.slider: Slider | None = None
        self.select_label: Html | None = None
        self.slider_container = None

    def sync_selector_to_dim(self):
        """Push dim.option to the UI selector."""
        if self.selector is not None:
            self.selector.value = self.dim.option
            self.selector.update()

    def sync_label_to_dim(self):
        """Push dim.name to the UI selector label."""
        if self.selector is not None:
            self.selector.label = self.dim.name.replace("__", ".")

    def update_slider_max(self, max_val: int):
        """Update the slider's max value."""
        if self.slider is not None:
            self.slider._props["max"] = max_val
            self.slider.update()

    def delete_slider(self):
        """Remove slider and label from the UI."""
        if self.slider is not None:
            self.slider.delete()
            self.slider = None
        if self.select_label is not None:
            self.select_label.delete()
            self.select_label = None

    def build_slider(self, run: BaseRun, on_plot):
        """Build the slider and value label for select_value mode."""
        dim = self.dim
        dim_size = run.full_data_set.sizes[dim.name]
        with ui.row().classes("w-full items-center"):
            with ui.column().classes('flex-grow'):
                self.slider = ui.slider(
                    min=0, max=dim_size - 1, step=1, value=dim.select_index,
                    on_change=lambda e: run.update_subset_dims(dim, 'select_value', e.value),
                ).classes('flex-grow').props('color="purple" markers')
            self.select_label = ui.html(content='', sanitize=False).classes(
                'shrink-0 text-right px-2 py-1 bg-purple text-white '
                'rounded-lg text-xs font-normal text-center')
            self._update_label_text(run, plot=False)
            self.slider.on(
                'update:model-value',
                lambda e: self._on_slider_change(run, on_plot),
                throttle=0.2, leading_events=False)

    def _update_label_text(self, run: BaseRun, plot: bool = True):
        """Update the label showing the current slider value with units."""
        if self.select_label is None or self.slider is None:
            return
        label_txt = f' {unit_formatter(run, self.dim, self.slider.value)} '
        self.select_label.set_content(label_txt)

    def _on_slider_change(self, run: BaseRun, on_plot):
        """Handle slider value change: update label and trigger replot."""
        self._update_label_text(run)
        on_plot()
