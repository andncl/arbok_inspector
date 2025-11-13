import time
from dataclasses import dataclass
from nicegui import ui, app

from arbok_inspector.state import inspector
from arbok_inspector.pages.run_view import run_page
from arbok_inspector.widgets.update_day_selecter import update_day_selecter
from arbok_inspector.widgets.build_run_selecter import build_run_selecter

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
# RUN_PARAM_DICT = {
#     'run_id': 'Run ID',
#     'exp_id': 'Experiment ID',
#     'result_counter': '# results',
#     'run_timestamp': 'Started',
#     'completed_timestamp': 'Completed',
# }
AGGRID_STYLE = 'height: 95%; min-height: 0;'
EXPANSION_CLASSES = 'w-full p-0 gap-1 border border-gray-400 rounded-lg no-wrap items-start'
DEFAULT_REFRESH_INTERVAL_S = 0.5

@ui.page('/browser')
async def database_browser_page():
    """Database general page showing the selected database"""
    _ = await ui.context.client.connected()
    if inspector.database_type is None:
        ui.navigate.to('/')
    app.storage.tab['last_selected_day'] = None
    app.storage.general["avg_axis"] = 'iteration'
    app.storage.general["result_keywords"] = None
    app.storage.tab["avg_axis_input"] = None
    app.storage.tab["result_keyword_input"] = None
    offset_minutes = await ui.run_javascript('new Date().getTimezoneOffset()')
    offset_hours = -float(offset_minutes) / 60
    app.storage.general["timezone"] = offset_hours
    print(f"TIMEZONE: UTC{offset_hours}")

    grids = {'day': None, 'run': None}
    with ui.column().classes('w-full h-screen'):
        ui.add_head_html('<title>Arbok Inspector - Database general</title>')
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Arbok Inspector').classes('text-3xl font-bold mb-1')
            
            with ui.expansion('Database info and settings', icon='info', value=True)\
                .classes(EXPANSION_CLASSES).props('expand-separator'):
                build_database_info_section(grids)

        with ui.row().classes('w-full flex-1'):
            build_day_selecter(grids)
            app.storage.tab['run_selecter'] = ui.column().classes('flex-1').classes('h-full')
            trigger_rebuild_run_selecter(day = None)

def open_run_page(run_id: int):
    app.storage.general["avg_axis"] = app.storage.tab["avg_axis_input"].value
    app.storage.general["result_keywords"] = app.storage.tab["result_keyword_input"].value
    print(f"Result Keywords:")
    print(app.storage.general['result_keywords'])
    ui.navigate.to(f'/run/{run_id}', new_tab=True)

def build_database_info_section(grids):
    """Build the database information and settings section."""
    with ui.row().classes('w-full'):
        build_info_section()
        build_actions_section()
        build_settings_section(grids)

def build_info_section():
    """Build the database information section."""
    with ui.card().classes('w-1/3'):
        ui.label('Database Information').classes('text-xl font-semibold mb-4')
        if inspector.database_type == 'qcodes':
            _build_qcodes_db_info_section()
        elif inspector.database_type == 'native':
            _build_native_db_info_section()

def _build_qcodes_db_info_section():
    if inspector.qcodes_database_path:
        ui.label(f'Database Path: {str(inspector.qcodes_database_path)}')
       
def _build_native_db_info_section():
    ui.label(f'Native database info placeholder')

def build_actions_section():
    with ui.card().classes('w-1/4 h-full'):
        with ui.column().classes('w-full justify-start'):
            ui.button(
                text = 'Select New Database',
                on_click=lambda: ui.navigate.to('/'),
                color='purple').props('dense').classes()
            ui.button(
                text = 'Reload',
                on_click=lambda: update_day_selecter(grids['day']),
                color = '#4BA701'
                ).props('dense').classes()
            timer = ui.timer(
                interval=DEFAULT_REFRESH_INTERVAL_S,
                callback=  lambda: trigger_rebuild_run_selecter(None), #build_day_selecter(None),
                active=False
                )
            # ui.label('Auto-plot')
            ui.switch(
                on_change=lambda e: setattr(timer, 'active', e.value)
            )
            ui.number(
                # label='(s)',
                value=DEFAULT_REFRESH_INTERVAL_S,
                min=0.1,
                step=0.1,
                format='%.1f',
                on_change=lambda e: on_interval_change(e, timer),
            ).props('dense suffix="s"').classes('w-12')

def on_interval_change(e, timer):
    try:
        value = float(e.value)
        if value < 0.1:
            ui.notify('Interval must be at least 0.1 s', color='red')
            e.sender.value = timer.interval  # revert
            return
        timer.interval = value
        ui.notify(f'Refresh interval set to {value:.2f} s', color='green')
    except ValueError:
        ui.notify('Please enter a valid number', color='red')
        e.sender.value = timer.interval  # revert

def build_settings_section(grids):
    """Build the database settings section."""
    with ui.card().classes('w-1/3'):
        with ui.row().classes('w-full'):
            app.storage.tab["result_keyword_input"] = ui.input(
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
            app.storage.tab["avg_axis_input"] = ui.input(
                label = 'average-axis keyword',
                value = "iteration"
                ).props('rounded outlined dense')\
                .classes('w-full')


def build_day_selecter(grids):
    """Build the day selecter grid."""
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
                handler = lambda event: trigger_rebuild_run_selecter(event.args["value"])
            )
        update_day_selecter(grids['day'])

def trigger_rebuild_run_selecter(day):
    ### TODO: make this an aggrid update! Not rebuild. Its very flashy!
    print(day)
    if day is None:
        day = app.storage.tab['last_selected_day']
    build_run_selecter(day)
    app.storage.tab['last_selected_day'] = day
