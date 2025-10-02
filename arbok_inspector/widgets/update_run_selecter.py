from datetime import datetime
from nicegui import ui

from arbok_inspector.state import inspector

def update_run_selecter(run_grid, run_timestamp, run_grid_column_defs):
    inspector.cursor.execute("""
        SELECT *
        FROM runs
        WHERE DATE(datetime(run_timestamp, 'unixepoch')) = ?
        ORDER BY run_timestamp;
        """, (run_timestamp,))
    runs = inspector.cursor.fetchall()
    results = [dict(row) for row in runs]

    run_grid_rows = []
    columns = [x['field'] for x in run_grid_column_defs]
    for run in results:
        print(f'Run: {run.keys()}')
        run_dict = {}
        for key in columns:
            if key in run:
                value = run[key]
                if 'time' in key:
                    value = datetime.utcfromtimestamp(value).strftime('%H:%M:%S') if value is not None else 'N/A'
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

