from datetime import datetime, timedelta
from nicegui import ui, app
from sqlalchemy import text

from arbok_inspector.state import inspector

def update_run_selecter(run_grid, target_day, run_grid_column_defs):
    offset_hours = app.storage.general["timezone"]
    print(f"Showing runs from {target_day}")
    if inspector.database_type == 'qcodes':
        rows = get_qcodes_runs_for_day(inspector.cursor, target_day, offset_hours)
    else:
        rows = get_native_arbok_runs_for_day(inspector.database_engine, target_day, offset_hours)
    run_grid_rows = []
    columns = [x['field'] for x in run_grid_column_defs]
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

    run_grid.options['rowData'] = run_grid_rows
    run_grid.update()

    ui.notify(
        'Run selector updated: \n'
        f'found {len(run_grid_rows)} run(s)',
        type='positive',
        multi_line=True,
        classes='multi-line-notification',
        position = 'top-right'
    )

def get_qcodes_runs_for_day(
    cursor, target_day: str, offset_hours: float) -> list[dict]:
    """
    Fetch runs from a QCoDeS database
    Args:
        cursor: SQLite cursor connected to the database
        target_day (str): The target day in 'YYYY-MM-DD'
        offset_hours (float): The timezone offset in hours
    Returns:
        list[dict]: List of runs as dictionaries
    """
    cursor.execute(
        f"""
        SELECT *
        FROM runs
        WHERE DATE(datetime(run_timestamp, 'unixepoch', '{offset_hours} hours')) = ?
        ORDER BY run_timestamp;
        """,
        (target_day,),
    )
    rows = cursor.fetchall()
    return [dict(row) for row in rows]
     

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
        SELECT *
        FROM runs
        WHERE (to_timestamp(start_time) + (:offset_hours || ' hours')::interval)::date = :target_day
        ORDER BY start_time;
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"offset_hours": offset_hours, "target_day": target_day})

    rows_as_dicts = [dict(row) for row in result.mappings()]
    return rows_as_dicts