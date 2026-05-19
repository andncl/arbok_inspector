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
        self.fft_range_element = None
        self.fft_repr_select = None

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

    def delete_fft_controls(self):
        """Remove all FFT UI controls."""
        if self.fft_range_element is not None:
            self.fft_range_element.delete()
            self.fft_range_element = None
        if self.fft_repr_select is not None:
            self.fft_repr_select.delete()
            self.fft_repr_select = None

    def build_fft_controls(self, run: BaseRun, on_plot):
        """Build the FFT representation selector and frequency range slider."""
        dim_size = run.full_data_set.sizes[self.dim.name]
        freq_count = dim_size // 2 + 1
        if run.fft_freq_range is None:
            run.fft_freq_range = {'min': 1, 'max': freq_count - 1}
        repr_labels = {'PSD': 'PSD', 'Amplitude': 'Amp', 'Real': 'Re', 'Imaginary': 'Im'}
        self.fft_repr_select = ui.toggle(
            repr_labels,
            value=run.fft_representation,
            on_change=lambda e: self._on_fft_repr_change(run, e.value, on_plot),
        ).props('dense size="sm" toggle-color=purple no-caps spread').classes('w-full')
        self.fft_range_element = ui.range(
            min=0, max=freq_count - 1, step=1,
            value={'min': float(run.fft_freq_range['min']),
                   'max': float(run.fft_freq_range['max'])},
        ).props('label-always snap color="purple" markers')
        self.fft_range_element.on(
            'update:model-value',
            lambda: self._on_fft_range_change(run, on_plot),
            throttle=0.3, leading_events=False)

    def _on_fft_repr_change(self, run: BaseRun, value: str, on_plot):
        """Handle representation change — recalculates FFT with new output."""
        run.fft_representation = value
        on_plot()

    def _on_fft_range_change(self, run: BaseRun, on_plot):
        """Handle frequency range change — replot without recalculating FFT."""
        if self.fft_range_element is not None:
            val = self.fft_range_element.value
            run.fft_freq_range = {'min': int(val['min']), 'max': int(val['max'])}
        on_plot()

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
