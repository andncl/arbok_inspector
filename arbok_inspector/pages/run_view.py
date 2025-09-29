from nicegui import ui
from qcodes.dataset import load_by_id
import plotly.graph_objects as go

from arbok_inspector.analysis.prepare_data import prepare_and_avg_data
from arbok_inspector.analysis.analysis_base import AnalysisBase

run_table_columns = [
    {'field': 'name', 'filter': 'agTextColumnFilter', 'floatingFilter': True},
    {'field': 'size'},
    {'field': 'x', 'checkboxSelection': True},
    {'field': 'y', 'checkboxSelection': True},
    {'field': 'average', 'checkboxSelection': True},
]


class Run:
    def __init__(self, run_id: int):
        self.run_id = run_id
        self.full_data_set = load_by_id(run_id).to_xarray_dataset()
        self.full_sub_set = None
        self.dims = list(self.full_data_set.coords.keys())
        self.x_axis = self.dims[-1] if len(self.dims) > 0 else None
        self.y_axis = self.dims[-2] if len(self.dims) > 1 else None
        self.subset_dims = {name: None for name in self.full_data_set.dims}

    def display_summary(self):
        ui.html(self.full_data_set._repr_html_())

    def update_subset_dims(self, coord, action, selection = None):
        self.subset_dims[coord] = action
        ui.notify(f'Updated subset with {action} on {coord}')

    def generate_subset(self, readout):
        sub_set = self.full_data_set[readout]
        for dim, action in self.subset_dims.items():
            if action == 'average':
                sub_set = sub_set.mean(dim=dim)
            elif action == 'x-axis':
                self.x_axis = dim
            elif action == 'y-axis':
                self.y_axis = dim
            elif action == 'select_element' and selection is not None:
                sub_set = sub_set.sel({dim: selection})
        self.full_sub_set = sub_set
        return sub_set

    def add_plot(self, readout_name: str):
        subset = self.generate_subset(readout_name)
        if len(subset.dims) > 2:
            ui.notify(
                f'Cannot plot more than 2D data (is {len(subset.dims)})'
                " Please reduce dimensions first.",
                type='negative'
            )
        
        fig = go.Figure(data=go.Heatmap(
            z=subset.to_numpy(),
            colorscale='Viridis',  # nice color scale, you can choose others like 'Cividis', 'Hot', etc.
            colorbar=dict(title='Intensity')
        ))
        return fig

    def select_index(self, dim, index):
        # if dim in self.full_data_set.dims:
        value = self.full_data_set[dim].values[index]

class RunResult(AnalysisBase):
    def __init__(self, run: Run, readout_name: str):
        self.run_id = run.run_id
        self.readout_name = readout_name
        self.run_id, self.xr_data, self.np_data = prepare_and_avg_data(run_id, readout_name)

expansion_style = 'w-full max-w-2xl mx-auto my-4 border border-gray-300 rounded-lg shadow-md'

@ui.page('/run/{run_id}')
async def run_page(run_id: str):
    """Display details for a specific run"""
    run = Run(int(run_id))
    ui.label(f'Run Page for ID: {run_id}').classes('text-2xl font-bold mb-6')
    
    with ui.row().classes('w-full max-w-2xl mx-auto p-4'):
        ui.label("Coordinates:").classes('text-lg font-semibold')
        # run_table_rows = []
        for i, dim in enumerate(run.full_data_set.dims):
            if i == len(run.full_data_set.dims) - 1:
                selection = 4
            elif i == len(run.full_data_set.dims) - 2:
                selection = 3
            else:
                selection = 2
            if 'iteration' in dim:
                selection = 1
            with ui.row().classes('w-full items-center mb-2'):
                add_dim_dropdown(dim, run, selection)
    
    with ui.row().classes('w-full max-w-2xl mx-auto p-4'):
        container = ui.row().classes('w-full')
        with ui.dropdown_button("Add plot", auto_close = True, color = 'green'):
            for result in run.full_data_set:
                ui.item(f'{result.replace("__", ".")}', on_click=lambda d=result: add_plot_ui(run, d, container))
    
    with ui.expansion('xarray summary', icon='expand_more', value = True).classes(expansion_style):
        run.display_summary()

def add_dim_dropdown(dim: str, run: Run, selection: int):
    # with ui.column().classes('mr-4'):
    #     ui.label(f'{dim.replace("__", ".")}')
    with ui.row().classes('w-full'):
        with ui.column().classes('w-1/2'):
            select_placeholder = ui.column().classes('flex')
        with ui.column().classes('w-1/3'):
            with ui.row():
                slider_placeholder = ui.column().classes('flex')
            with ui.row().classes('w-1/6'):
                label_placeholder = ui.column().classes('flex')
        placeholders = (slider_placeholder, label_placeholder)
        ui.select(
            options = {1: 'average', 2: 'select value', 3: 'y-axis', 4: 'x-axis'},
            value = selection,
            label = f'{dim.replace("__", ".")}',
            on_change = lambda e: update_dim_selection(run, dim, e.value, placeholders)
        ).classes('w-1/2').parent = select_placeholder

def update_dim_selection(run: Run, dim: str, value, placeholder):
    placeholder[0].clear()
    placeholder[1].clear()
    if value == 2:
        dim_size = run.full_data_set.sizes[dim]
        slider = ui.slider(
            min=0, max=dim_size - 1, step=1, value=0,
            # on_change=lambda e: print(e.value)
        ).classes('w-1/2')
        slider.props('label-always')
        slider.parent = placeholder[0]
        slider.on(
            'update:model-value', lambda e: update_value_from_slider(label, slider, run, dim),
            throttle=0.2, leading_events=False)
        label = ui.label(f'Value: {run.full_data_set[dim].values[0]}').classes('ml-4')
        ui.label().bind_text_from(slider, 'value')

def update_value_from_slider(label, slider, run: Run, dim: str):
    label.text = f'Value: {run.full_data_set[dim].values[slider.value]}'
    run.select_index(dim, slider.value)

    lambda e: run.select_index(dim, e.args)
def add_plot_ui(run, readout, container):
    print('plotting!!!')
    with ui.row().classes('w-full max-w-2xl mx-auto my-4'):
        ui.button('Close plot', on_click=lambda: plot_card.delete(), color = 'red').classes('ml-auto mb-2')
    fig = run.add_plot(readout)
    ui_fig = ui.plotly(fig).classes('w-full max-w-2xl mx-auto mb-4')
    ui_fig.parent = container



        #     x, y = False, False
        #     if i == len(run.full_data_set.dims) - 1:
        #         x = True
        #     elif i == len(run.full_data_set.dims) - 2:
        #         y = True
        #     run_table_rows.append({
        #         'name': dim.replace("__", "."),
        #         'size': run.full_data_set.sizes[dim],
        #         'x': x,
        #         'y': y,
        #         'average': 'average' if run.subset_dims[dim] == 'average' else '',
        #     })
        # grid = ui.aggrid({
        #     'columnDefs': run_table_columns,
        #     'rowData': run_table_rows,
        #     ':getRowId': '(params) => params.data.name',
        #     "rowSelection": "multiple",
        #     "defaultColDef": {"resizable": True, "sortable": True},
        # }).classes('w-full max-w-2xl')