from nicegui import ui
from arbok_inspector.state import inspector
from arbok_inspector.pages.run_view import run_page
from arbok_inspector.widgets.update_day_selecter import update_day_selecter
from arbok_inspector.widgets.update_run_selecter import update_run_selecter

day_grid_column_defs = [
    {'headerName': 'Day', 'field': 'day'},
]

run_grid_column_defs = [
    {'headerName': 'Run ID', 'field': 'run_id'},
    {'headerName': 'Experiment ID', 'field': 'exp_id'},
    {'headerName': '# Results', 'field': 'result_counter'},
    {'headerName': 'Started', 'field': 'run_timestamp'},
    {'headerName': 'Completed', 'field': 'completed_timestamp'},
]

run_param_dict = {
    'run_id': 'Run ID',
    'exp_id': 'Experiment ID',
    'result_counter': '# results',
    'run_timestamp': 'Started',
    'completed_timestamp': 'Completed',
}

@ui.page('/browser')
def database_browser_page():
    """Database browser page showing the selected database"""
    ui.add_head_html('<title>Arbok Inspector - Database Browser</title>')


    with ui.column().classes('w-full'):

        with ui.row().classes('flex max-w-2xl mx-auto mt-8 p-4'): #'w-full max-w-2xl mx-auto mt-8 p-4'):
            ui.label('Arbok Inspector').classes('text-3xl font-bold mb-6')
            
            with ui.card().classes('w-full p-6'):
                ui.label('Database Information').classes('text-xl font-semibold mb-4')
                if inspector.database_path:
                    ui.label(f'Database Path: {str(inspector.database_path)}').classes('text-lg')
                else:
                    ui.label('No database selected').classes('text-lg text-red-500')
                
                # Button to select a new database
                ui.button('Select New Database', 
                        on_click=lambda: ui.navigate.to('/'),
                        color='purple').classes('mt-4')

        with ui.row().classes('flex'):
            with ui.column().classes('flex bg-blue-100 p-4'):
                ui.label('Select a day!').classes('text-lg font-semibold mb')
                ui.button('Reload', on_click=lambda: update_day_selecter(day_grid)).classes('mb-2')
                day_grid = ui.aggrid({
                    'defaultColDef': {'flex': 1},
                    'columnDefs': day_grid_column_defs,
                    'rowData': {},
                    'rowSelection': 'multiple',
                }).classes('max-h-40').on(
                    'cellClicked', lambda event: update_run_selecter(run_grid, event.args["value"], run_grid_column_defs))
                update_day_selecter(day_grid)

            with ui.column().classes('flex bg-blue-100 p-4'):
                ui.label('Select a run from the db! ---------------------------------').classes('text-lg font-semibold mb-2')
                run_grid = ui.aggrid({
                    'defaultColDef': {'flex': 1},
                    'columnDefs': run_grid_column_defs,
                    'rowData': {},
                    'rowSelection': 'multiple',
                }).classes('max-h-40').on(
                    'cellClicked',
                    lambda event: open_run_page(event.args['data']['run_id'])
                )

def open_run_page(run_id: int):
    ui.navigate.to(f'/run/{run_id}', new_tab=True)
