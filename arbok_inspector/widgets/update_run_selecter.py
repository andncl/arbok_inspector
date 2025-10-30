from datetime import datetime, timedelta
from nicegui import ui, app

from arbok_inspector.state import inspector

def update_run_selecter(run_grid, target_day, run_grid_column_defs):
    offset_hours = app.storage.general["timezone"]
    print(target_day)
    print(offset_hours)
    inspector.cursor.execute(
        f"""
        SELECT *
        FROM runs
        WHERE DATE(datetime(run_timestamp, 'unixepoch', '{offset_hours} hours')) = ?
        ORDER BY run_timestamp;
        """,
        (target_day,),
    )
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
                    if value is not None:
                        # Apply offset and format nicely
                        local_dt = datetime.utcfromtimestamp(value) + timedelta(hours=offset_hours)
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

