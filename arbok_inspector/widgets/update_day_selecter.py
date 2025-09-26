from datetime import datetime
from nicegui import ui

from arbok_inspector.state import inspector

def update_day_selecter(day_grid):
    inspector.cursor.execute("""
        SELECT 
            day,
            MIN(run_timestamp) AS earliest_ts
        FROM (
            SELECT 
                run_timestamp,
                DATE(datetime(run_timestamp, 'unixepoch')) AS day
            FROM runs
        )
        GROUP BY day
        ORDER BY day;
    """)
    rows = inspector.cursor.fetchall()
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
