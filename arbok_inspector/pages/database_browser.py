from nicegui import ui, app
from arbok_inspector.state import inspector
from arbok_inspector.pages.run_view import run_page
from arbok_inspector.widgets.update_day_selecter import update_day_selecter
from arbok_inspector.widgets.update_run_selecter import update_run_selecter

DAY_GRID_COLUMN_DEFS = [
    {'headerName': 'Day', 'field': 'day'},
]

small_col_width = 30
RUN_GRID_COLUMN_DEFS = [
    {'headerName': 'Run ID', 'field': 'run_id', "width": small_col_width},
    {'headerName': 'Name', 'field': 'name'},
    {'headerName': 'Exp ID', 'field': 'exp_id', "width": small_col_width},
    {'headerName': '# Results', 'field': 'result_counter', "width": small_col_width},
    {'headerName': 'Started', 'field': 'run_timestamp', "width": small_col_width},
    {'headerName': 'Finish', 'field': 'completed_timestamp', "width": small_col_width},
]
RUN_PARAM_DICT = {
    'run_id': 'Run ID',
    'exp_id': 'Experiment ID',
    'result_counter': '# results',
    'run_timestamp': 'Started',
    'completed_timestamp': 'Completed',
}
AGGRID_STYLE = 'height: 95%; min-height: 0;'
EXPANSION_CLASSES = 'w-full p-0 gap-1 border border-gray-400 rounded-lg no-wrap items-start'

@ui.page('/browser')
def database_browser_page():
    """Database browser page showing the selected database"""
    grids = {'day': None, 'run': None}
    with ui.column().classes('w-full h-screen'):
        ui.add_head_html('<title>Arbok Inspector - Database Browser</title>')
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Arbok Inspector').classes('text-3xl font-bold mb-6')
            
            with ui.expansion('Database info and settings', icon='info', value=True)\
                .classes(EXPANSION_CLASSES).props('expand-separator'):
                with ui.row().classes('w-full'):
                    with ui.column().classes('w-1/3'):
                        ui.label('Database Information').classes('text-xl font-semibold mb-4')
                        if inspector.database_path:
                            ui.label(f'Database Path: {str(inspector.database_path)}').classes()
                        else:
                            ui.label('No database selected').classes('text-lg text-red-500')
                        
                        # Button to select a new database
                    with ui.column().classes('w-1/2'):
                        with ui.row().classes('w-full'):
                            result_input = ui.input(
                                label = 'auto-plot keywords',
                                placeholder="e.g:\t\t[ ( 'Q1' , 'state' ), 'feedback' ]"
                                ).props('rounded outlined dense')\
                                .classes('w-full')\
                                .tooltip("""
                                    Selects all results that contain the specified keywords in their name.<br>
                                    Can be a single keyword (string) or a tuple of keywords.<br>
                                    The latter one requires all keywords to be present in the result name.<br>

                                    The given example would select all results that contain 'Q1' and 'state' in their name<br>
                                    or all results that contain 'feedback' in their name.
                                """).props('v-html')
                            result_input = ui.input(
                                label = 'average-axis keyword',
                                value = "iteration"
                                ).props('rounded outlined dense')\
                                .classes('w-full')
                        with ui.row().classes('w-full justify-start'):
                            ui.button(
                                text = 'Select New Database',
                                on_click=lambda: ui.navigate.to('/'),
                                color='purple').classes()
                            ui.button(
                                text = 'Reload',
                                on_click=lambda: update_day_selecter(grids['day']),
                                color = '#4BA701'
                                ).classes()

        with ui.row().classes('w-full flex-1'):
            with ui.column().style('width: 120px;').classes('h-full'):
                grids['day'] = ui.aggrid(
                    {
                        'defaultColDef': {'flex': 1},
                        'columnDefs': DAY_GRID_COLUMN_DEFS,
                        'rowData': {},
                        'rowSelection': 'multiple',
                    },
                    theme = 'ag-theme-balham-dark')\
                    .classes('text-sm ag-theme-balham-dark')\
                    .style(AGGRID_STYLE)\
                    .on(
                        type = 'cellClicked',
                        handler = lambda event: update_run_selecter(
                            grids['run'], event.args["value"], RUN_GRID_COLUMN_DEFS)
                    )
                update_day_selecter(grids['day'])
            with ui.column().classes('flex-1').classes('h-full'):
                grids['run'] = ui.aggrid(
                    {
                        'defaultColDef': {'flex': 1},
                        'columnDefs': RUN_GRID_COLUMN_DEFS,
                        'rowData': {},
                        'rowSelection': 'multiple',
                    },
                    #theme = 'ag-theme-balham-dark'
                ).classes('ag-theme-balham-dark').style(
                    AGGRID_STYLE
                ).on(
                    'cellClicked',
                    lambda event: open_run_page(event.args['data']['run_id'])
                )

def open_run_page(run_id: int):
    ui.navigate.to(f'/run/{run_id}', new_tab=True)
