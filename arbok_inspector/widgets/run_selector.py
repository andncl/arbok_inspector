import json
from datetime import datetime, timedelta

from nicegui import ui, app
from sqlalchemy import text

from arbok_inspector.state import inspector

small_col_width = 50
med_col_width = 60

QCODES_RUN_GRID_COLUMN_DEFS = [
    {'headerName': 'Run ID', 'field': 'run_id', "width": small_col_width},
    {'headerName': 'Name', 'field': 'name'},
    {'headerName': 'Experiment', 'field': 'experiment_name'},
    {'headerName': '# Results', 'field': 'result_counter', "width": small_col_width},
    {'headerName': 'Started', 'field': 'run_timestamp', "width": small_col_width},
    {'headerName': 'Finish', 'field': 'completed_timestamp', "width": small_col_width},
]
NATIVE_RUN_GRID_COLUMN_DEFS = [
    {'headerName': 'Run ID', 'field': 'run_id', "width": small_col_width},
    {'headerName': 'Name', 'field': 'name'},
    {'headerName': 'Experiment', 'field': 'experiment'},
    {'headerName': '# results', 'field': 'result_count', "width": med_col_width},
    {'headerName': '# batches', 'field': 'batch_count', "width": med_col_width},
    {'headerName': 'started', 'field': 'start_time', "width": med_col_width},
    {'headerName': 'last result', 'field': 'completed_time', "width": med_col_width},
]
AGGRID_STYLE = 'height: 95%; min-height: 0;'

def build_run_selector(target_day: str | None = None) -> ui.aggrid:
    """Build the run selector grid for the specified day."""
    if target_day is None:
        target_day: str = app.storage.tab.get('last_selected_day')
    run_grid_rows, run_grid_columns = get_run_grid_data(target_day)
    run_grid = ui.aggrid(
            {
                'defaultColDef': {'flex': 1, 'minWidth': 50},
                'columnDefs': run_grid_columns,
                'rowData': run_grid_rows,
                'rowSelection': 'multiple',
            },
        ).classes('ag-theme-balham-dark').style(
            AGGRID_STYLE
        ).on(
            'cellClicked',
            lambda event: open_run_page(event.args['data']['run_id'])
        )
    ui.notify(
        'Run selector updated: \n'
        f'found {len(run_grid_rows)} run(s)',
        type='positive',
        multi_line=True,
        classes='multi-line-notification',
        position = 'top-right'
    )
    return run_grid

def update_run_selector(target_day: str | None = None) -> None:
    """Update the run selector grid based on the last selected day."""
    if target_day is None:
        target_day: str = app.storage.tab.get('last_selected_day')
    run_grid: ui.aggrid = app.storage.tab.get('run_grid')
    run_grid_rows, _ = get_run_grid_data(target_day)
    ui.run_javascript(f"""
        const grid = getElement('{run_grid.id}');
        if (grid && grid.api) {{
            grid.api.setGridOption('rowData', {json.dumps(run_grid_rows)});
        }}
    """)

def get_run_grid_data(target_day: str) -> tuple[list[dict], list[dict]]:
    """
    Fetch run data for the specified day from the database.
    
    Args:
        target_day (str): The target day in 'YYYY-MM-DD'
    Returns:
        tuple[list[dict], list[dict]]: A tuple containing the list of run data
        dictionaries and the list of column definitions.
    """
    offset_hours = app.storage.general["timezone"]
    run_grid_rows = []
    print(f"Showing runs from {target_day}")
    if inspector.database_type == 'qcodes':
        rows = get_qcodes_runs_for_day(inspector.cursor, target_day, offset_hours)
        run_grid_columns = QCODES_RUN_GRID_COLUMN_DEFS
    else:
        rows = get_native_arbok_runs_for_day(inspector.database_engine, target_day, offset_hours)
        run_grid_columns = NATIVE_RUN_GRID_COLUMN_DEFS
    run_grid_rows = []
    columns = [x['field'] for x in run_grid_columns]
    for run in rows:
        run_dict = {}
        for key in columns:
            if key in run:
                value = run[key]
                if 'time' in key:
                    if value is not None:
                        local_dt = datetime.utcfromtimestamp(value)
                        local_dt += timedelta(hours=offset_hours)
                        value = local_dt.strftime('%H:%M:%S')
                    else:
                        value = 'N/A'
                run_dict[key] = value
        run_grid_rows.insert(0, run_dict)
    return run_grid_rows, run_grid_columns

def get_qcodes_runs_for_day(
    cursor, target_day: str, offset_hours: float
) -> list[dict]:
    """
    Fetch runs from a QCoDeS (SQLite) database, joined with experiments,
    excluding the 'qua_program' and 'snapshot' columns entirely.
    """
    hours = int(offset_hours)
    minutes = int((offset_hours - hours) * 60)
    offset_str = f"{'+' if offset_hours >= 0 else '-'}{abs(hours):02d}:{abs(minutes):02d}"

    # get all columns except the ones we want to exclude
    exclude_columns = {'qua_program', 'snapshot'}
    cursor.execute("PRAGMA table_info(runs)")
    all_columns = [col['name'] for col in cursor.fetchall() if col['name'] not in exclude_columns]

    # construct SELECT statement
    columns_str = ", ".join(f"r.{col}" for col in all_columns)

    query = f"""
        SELECT {columns_str}, e.name AS experiment_name
        FROM runs r
        JOIN experiments e ON r.exp_id = e.exp_id
        WHERE DATE(datetime(r.run_timestamp, 'unixepoch', '{offset_str}')) = ?
        ORDER BY r.run_timestamp;
    """

    cursor.execute(query, (target_day,))
    rows = cursor.fetchall()
    row_dicts = [dict(row) for row in rows]
    return row_dicts

NATIVE_COLUMNS = {
    'run_id': 'run ID',
    'name': 'name',
    'result_count': '# results',
    'batch_count': '# batches',
    'start_time': 'started',
    'completed_time': 'last result',
    'is_completed': 'completed'
}

def get_native_arbok_runs_for_day(
    engine,
    target_day: str,
    offset_hours: float) -> list[dict]:
    """
    Fetch runs from a native Arbok database
    
    Args:
        engine: SQLAlchemy engine connected to the database
        target_day (str): The target day in 'YYYY-MM-DD'
        offset_hours (float): The timezone offset in hours
    Returns:
        list[dict]: List of runs as dictionaries
    """
    query = text("""
        SELECT r.*, e.name AS experiment_name
        FROM runs r
        JOIN experiments e ON r.exp_id = e.exp_id
        WHERE (to_timestamp(r.start_time) + (:offset_hours || ' hours')::interval)::date = :target_day
        ORDER BY r.start_time;
    """)

    with engine.connect() as conn:
        result = conn.execute(
            query, {"offset_hours": offset_hours, "target_day": target_day}
        )
        runs_filtered = [
            {**{col: row[col] for col in NATIVE_COLUMNS.keys()},
            "experiment": row["experiment_name"]}
            for row in result.mappings()
        ]

    return runs_filtered

def open_run_page(run_id: int):
    app.storage.general["avg_axis"] = app.storage.tab["avg_axis_input"].value
    app.storage.general["result_keywords"] = app.storage.tab["result_keyword_input"].value
    print(f"Result Keywords:")
    print(app.storage.general['result_keywords'])
    ui.navigate.to(f'/run/{run_id}', new_tab=True)