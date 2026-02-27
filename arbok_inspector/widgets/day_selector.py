"""Module containing day selector grid generation and update functions"""
from datetime import datetime
from nicegui import ui, app
from sqlalchemy import text

from arbok_inspector.state import inspector
from arbok_inspector.widgets.run_selector import update_run_selector

DAY_GRID_COLUMN_DEFS = [
    {'headerName': 'Day', 'field': 'day'},
]

AGGRID_STYLE = 'height: 95%; min-height: 0;'

async def trigger_update_run_selector(day):
    print(f"day: {day}")
    if day is None:
        if 'last_selected_day' in app.storage.tab:
            day = app.storage.tab['last_selected_day']
        else:
            return
    await update_run_selector(day)
    app.storage.tab['last_selected_day'] = day

def build_day_selector() -> ui.aggrid:
    """Build the day selector grid."""
    day_grid = ui.aggrid(
        {
            'columnDefs': DAY_GRID_COLUMN_DEFS,
            'rowData': {},
            'theme': 'balham'
        },)\
        .classes('text-sm ag-theme-balham-dark')\
        .style(AGGRID_STYLE)\
        .on(
            type = 'cellClicked',
            handler = lambda event: trigger_update_run_selector(event.args["value"])
        )
    update_day_selector(day_grid)
    return day_grid

def update_day_selector(day_grid: ui.aggrid | None = None) -> None:
    """Update the day selector grid with available days from the database."""
    if day_grid is None:
        if 'day_grid' not in app.storage.tab:
            print("No day grid found in storage, cannot update.")
            return
        day_grid: ui.aggrid = app.storage.tab['day_grid']
    offset_hours = app.storage.general["timezone"]
    if inspector.database_type == 'qcodes':
        rows = get_qcodes_days(offset_hours)
    elif inspector.database_type == 'native_arbok':
        rows = get_native_arbok_days(inspector.database_engine,offset_hours)
    else:
        raise ValueError(f"Invalid database type: {inspector.database_type}")

    day_grid.clear()
    row_data = []
    for day, _ in rows[::-1]:
        row_data.append({'day': day})
    if app.storage.tab["last_selected_day"] is None:
        app.storage.tab["last_selected_day"] = rows[-1][0]
        print(f"No last day selected yet, setting to {rows[-1][0]}")
    day_grid.options['rowData'] = row_data
    day_grid.update()
    ui.notify(
        'Day selector updated: \n'
        f'found {len(row_data)} days',
        type='positive',
        multi_line=True,
        classes='multi-line-notification',
        position = 'top-right'
    )

def get_qcodes_days(offset_hours: float) -> list[tuple[str, datetime]]:
    """Retrieve available days from a QCoDeS database, adjusted for timezone offset."""
    import sqlite3
    conn = sqlite3.connect(inspector.qcodes_database_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                day,
                MIN(run_timestamp) AS earliest_ts
            FROM (
                SELECT 
                    run_timestamp,
                    DATE(datetime(run_timestamp, 'unixepoch', ? || ' hours')) AS day
                FROM runs   
            )
            GROUP BY day
            ORDER BY day;
        """, (offset_hours,))
        return cursor.fetchall()
    finally:
        conn.close()

def get_native_arbok_days(engine, offset_hours: float) -> list[tuple[str, datetime]]:
    """Retrieve available days from a native Arbok database, adjusted for timezone offset."""
    query = text("""
        SELECT 
            day,
            MIN(start_time) AS earliest_ts
        FROM (
            SELECT 
                start_time,
                (to_timestamp(start_time) + (:offset_hours || ' hours')::interval)::date AS day
            FROM runs
        ) AS sub
        GROUP BY day
        ORDER BY day;
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"offset_hours": offset_hours})
        return result.fetchall()
