"""
Dialog for editing JSON plot settings.
"""
import copy
import json
import importlib.resources as resources

from nicegui import app, ui

from arbok_inspector.widgets.build_xarray_grid import build_xarray_grid

class JsonPlotSettingsDialog:
    """
    Dialog for editing JSON plot settings.
    """
    def __init__(self, dimension: str):
        self.dimension = dimension
        self.json_editor = None
        self.dialog = self.build_plot_settings_dialog()

    def build_plot_settings_dialog(self):
        """
        Build the dialog for plot settings.
        """
        plot_dict = app.storage.tab[self.dimension]

        with ui.dialog() as dialog, ui.card():
            with ui.column().classes('w_full h-screen'):
                ui.label('Plot Settings')
                self.json_editor = ui.json_editor(
                    properties = {"content": {"json": plot_dict}},
                ).classes("jse-theme-dark")
                with ui.row().classes('w-full justify-end'):
                    ui.button(
                        text = 'Apply',
                        on_click=lambda: self.set_editor_data(),
                        color='green'
                        )
                    ui.button(
                        text = 'Reset',
                        on_click=lambda: self.reset_plot_settings(),
                        color='blue'
                        )
                    ui.button(
                        text = 'Close',
                        color = 'red',
                        on_click=dialog.close
                        )
        return dialog

    def open(self):
        """Open the dialog."""
        print("Opening dialog and setting json data")
        self.dialog.open()
        self.json_editor.properties['content']['json'] = copy.deepcopy(
            app.storage.tab[self.dimension])
        self.json_editor.update()

    async def set_editor_data(self):
        """Sets json data from the JSON editor to the app storage and rebuilds plots."""
        json_data = await self.json_editor.run_editor_method('get')
        json_data = json_data["json"]
        app.storage.tab[self.dimension] = json_data
        build_xarray_grid()

    def reset_plot_settings(self):
        """Reset plot settings to defaults."""
        if self.dimension == 'plot_dict_1D':
            with resources.files("arbok_inspector.configurations").joinpath("1d_plot.json").open("r") as f:
                app.storage.tab["plot_dict_1D"] = json.load(f)

        elif self.dimension == 'plot_dict_2D':
            with resources.files("arbok_inspector.configurations").joinpath("2d_plot.json").open("r") as f:
                app.storage.tab["plot_dict_2D"] = json.load(f)

        ui.notify('Reset to default settings', type='positive', position='top-right')
        build_xarray_grid()
