from datetime import datetime
from nicegui import ui, app
from sqlalchemy import text

from arbok_inspector.state import inspector

def update_day_selecter(day_grid):
    offset_hours = app.storage.general["timezone"]
    if inspector.database_type == 'qcodes':
        rows = get_qcodes_days(inspector.cursor, offset_hours)
    elif inspector.database_type == 'native_arbok':
        rows = get_native_arbok_days(inspector.database_engine,offset_hours)
    else:
        raise ValueError(f"Invalid database type: {inspector.database_type}")

    day_grid.clear()
    row_data = []
    for day, ts in rows[::-1]:
        row_data.append({'day': day})

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

def get_qcodes_days(cursor, offset_hours: float) -> list[tuple[str, datetime]]:
    cursor.execute(f"""
        SELECT 
            day,
            MIN(run_timestamp) AS earliest_ts
        FROM (
            SELECT 
                run_timestamp,
                DATE(datetime(run_timestamp, 'unixepoch', '{offset_hours} hours')) AS day
            FROM runs   
        )
        GROUP BY day
        ORDER BY day;
    """)
    return cursor.fetchall()

def get_native_arbok_days(engine, offset_hours: float) -> list[tuple[str, datetime]]:
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