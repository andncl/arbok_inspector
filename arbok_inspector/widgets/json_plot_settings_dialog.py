"""
Dialog for editing JSON plot settings.
"""
import copy
import json
import importlib.resources as resources

from nicegui import app, ui

from arbok_inspector.widgets.build_xarray_grid import build_xarray_grid

JSE_DARK_CSS = '''
.jse-theme-dark {
    --jse-theme-color: #2f6dd0; --jse-theme-color-highlight: #467cd2;
    --jse-background-color: #1e1e1e; --jse-text-color: #d4d4d4;
    --jse-text-color-inverse: #1e1e1e;
    --jse-panel-background: #252526; --jse-panel-border: #3c3c3c;
    --jse-panel-color: #d4d4d4;
    --jse-key-color: #9cdcfe; --jse-value-color: #ce9178;
    --jse-value-color-number: #b5cea8; --jse-value-color-boolean: #569cd6;
    --jse-value-color-null: #569cd6; --jse-value-color-string: #ce9178;
    --jse-delimiter-color: #808080; --jse-edit-outline: #467cd2;
    --jse-selection-background-color: #264f78;
    --jse-selection-background-inactive-color: #37373d;
    --jse-context-menu-background: #252526; --jse-context-menu-color: #d4d4d4;
    --jse-context-menu-border: #454545;
    --jse-context-menu-pointer-hover-background: #094771;
    --jse-menu-color: #d4d4d4;
}
'''

class JsonPlotSettingsDialog:
    """
    Dialog for editing JSON plot settings.
    """
    def __init__(self, dimension: str, storage: str = 'tab'):
        self.dimension = dimension
        self.storage = storage
        self.json_editor = None
        self.dialog = self.build_plot_settings_dialog()

    def _get_storage(self):
        return getattr(app.storage, self.storage)

    def build_plot_settings_dialog(self):
        """
        Build the dialog for plot settings.
        """
        plot_dict = self._get_storage()[self.dimension]

        with ui.dialog() as dialog, ui.card().classes('max-h-[100vh] max-w-[90vw]').style('overflow: hidden; background: #1e1e1e'):
            ui.add_css(JSE_DARK_CSS)
            with ui.row().classes('w-full h-full flex-nowrap').style('overflow: hidden'):
                with ui.column().classes('shrink-0 gap-2 justify-start'):
                    ui.label('Settings:').classes('font-semibold')
                    ui.button(
                        text='Apply',
                        on_click=lambda: self.set_editor_data(),
                        color='green'
                    ).props('dense')
                    ui.button(
                        text='Reset',
                        on_click=lambda: self.reset_plot_settings(),
                        color='blue'
                    ).props('dense')
                    ui.button(
                        text='Close',
                        color='red',
                        on_click=dialog.close
                    ).props('dense')
                self.json_editor = ui.json_editor(
                    properties={"content": {"json": plot_dict}, "mode": "text"},
                ).classes('jse-theme-dark flex-1 min-w-0').style(
                    'overflow: auto; max-height: 90vh')
        return dialog

    def open(self):
        """Open the dialog."""
        print("Opening dialog and setting json data")
        self.dialog.open()
        self.json_editor.properties['content']['json'] = copy.deepcopy(
            self._get_storage()[self.dimension])
        self.json_editor.update()

    async def set_editor_data(self):
        """Sets json data from the JSON editor to the app storage and rebuilds plots."""
        json_data = await self.json_editor.run_editor_method('get')
        if "json" in json_data:
            json_data = json_data["json"]
        else:
            json_data = json.loads(json_data["text"])
        self._get_storage()[self.dimension] = json_data
        ui.notify('Settings applied', type='positive', position='top-right')
        if self.storage == 'tab':
            build_xarray_grid()

    def reset_plot_settings(self):
        """Reset plot settings to defaults."""
        if self.dimension == 'plot_dict_1D':
            with resources.files("arbok_inspector.configurations").joinpath("1d_plot.json").open("r") as f:
                self._get_storage()["plot_dict_1D"] = json.load(f)
        elif self.dimension == 'plot_dict_2D':
            with resources.files("arbok_inspector.configurations").joinpath("2d_plot.json").open("r") as f:
                self._get_storage()["plot_dict_2D"] = json.load(f)
        ui.notify('Reset to default settings', type='positive', position='top-right')
        if self.storage == 'tab':
            build_xarray_grid()
