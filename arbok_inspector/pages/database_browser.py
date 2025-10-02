from nicegui import ui
from arbok_inspector.state import inspector
from arbok_inspector.pages.run_view import run_page
from arbok_inspector.widgets.update_day_selecter import update_day_selecter
from arbok_inspector.widgets.update_run_selecter import update_run_selecter

day_grid_column_defs = [
    {'headerName': 'Day', 'field': 'day'},
]

small_col_width = 30
run_grid_column_defs = [
    {'headerName': 'Run ID', 'field': 'run_id', "width": small_col_width},
    {'headerName': 'Name', 'field': 'name'},
    {'headerName': 'Exp ID', 'field': 'exp_id', "width": small_col_width},
    {'headerName': '# Results', 'field': 'result_counter', "width": small_col_width},
    {'headerName': 'Started', 'field': 'run_timestamp', "width": small_col_width},
    {'headerName': 'Finish', 'field': 'completed_timestamp', "width": small_col_width},
]

run_param_dict = {
    'run_id': 'Run ID',
    'exp_id': 'Experiment ID',
    'result_counter': '# results',
    'run_timestamp': 'Started',
    'completed_timestamp': 'Completed',
}
grids = {'day': None, 'run': None}

@ui.page('/browser')
def database_browser_page():
    """Database browser page showing the selected database"""
    with ui.column().classes('w-full h-screen'):
        ui.add_head_html('<title>Arbok Inspector - Database Browser</title>')
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Arbok Inspector').classes('text-3xl font-bold mb-6')
            
            with ui.card().classes('w-full p-2'):
                ui.label('Database Information').classes('text-xl font-semibold mb-4')
                if inspector.database_path:
                    ui.label(f'Database Path: {str(inspector.database_path)}').classes()
                else:
                    ui.label('No database selected').classes('text-lg text-red-500')
                
                # Button to select a new database
                with ui.row().classes('w-full justify-start'):
                    ui.button(
                        text = 'Select New Database',
                        on_click=lambda: ui.navigate.to('/'),
                        color='purple').classes()
                    ui.button(
                        text = 'Reload',
                        on_click=lambda: update_day_selecter(grids['day'])
                        ).classes()

        with ui.row().classes('w-full flex-1'):
            with ui.column().style('width: 120px;').classes('h-full'):
                grids['day'] = ui.aggrid(
                    {
                        'defaultColDef': {'flex': 1},
                        'columnDefs': day_grid_column_defs,
                        'rowData': {},
                        'rowSelection': 'multiple',
                    },
                    theme = 'ag-theme-balham-dark'
                ).classes('text-sm ag-theme-balham-dark').style(
                    #min_height
                ).on(
                    type = 'cellClicked',
                    handler = lambda event: update_run_selecter(grids['run'], event.args["value"], run_grid_column_defs)
                )
                update_day_selecter(grids['day'])
            with ui.column().classes('flex-1').classes('h-full'):
                grids['run'] = ui.aggrid(
                    {
                        'defaultColDef': {'flex': 1},
                        'columnDefs': run_grid_column_defs,
                        'rowData': {},
                        'rowSelection': 'multiple',
                    },
                    #theme = 'ag-theme-balham-dark'
                ).classes('ag-theme-balham-dark').style(
                    #min_height
                ).on(
                    'cellClicked',
                    lambda event: open_run_page(event.args['data']['run_id'])
                )

def open_run_page(run_id: int):
    ui.navigate.to(f'/run/{run_id}', new_tab=True)
