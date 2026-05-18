"""Module containing functions to build run selector grid"""
import json
from datetime import datetime, timedelta

from nicegui import ui, app
from nicegui import run as nicegui_run

from arbok_inspector.state import inspector

AGGRID_STYLE = 'height: 95%; min-height: 0;'


async def build_run_selector(target_day: str | None = None) -> ui.aggrid:
    """Build the run selector grid for the specified day."""
    if target_day is None:
        target_day: str = app.storage.tab.get('last_selected_day')
    run_grid_rows, run_grid_columns = await get_run_grid_data(target_day)
    run_grid = ui.aggrid(
        {
            'columnDefs': run_grid_columns,
            'rowData': run_grid_rows,
            'theme': 'balham',
        },
    ).style(
        AGGRID_STYLE
    ).on(
        'cellDoubleClicked',
        lambda event: open_run_page(event.args['data']['run_id'])
    )
    ui.notify(
        'Run selector updated: \n'
        f'found {len(run_grid_rows)} run(s)',
        type='positive',
        multi_line=True,
        classes='multi-line-notification',
        position='top-right'
    )
    return run_grid


async def update_run_selector(target_day: str | None = None) -> None:
    """Update the run selector grid based on the last selected day."""
    if target_day is None:
        target_day: str = app.storage.tab.get('last_selected_day')
    run_grid: ui.aggrid = app.storage.tab.get('run_grid')
    run_grid_rows, _ = await get_run_grid_data(target_day)
    ui.run_javascript(f"""
        const grid = getElement('{run_grid.id}');
        if (grid && grid.api) {{
            grid.api.setGridOption('rowData', {json.dumps(run_grid_rows)});
        }}
    """)


async def get_run_grid_data(target_day: str) -> tuple[list[dict], list[dict]]:
    """Fetch run data for the specified day from the database."""
    offset_hours = app.storage.general["timezone"]
    with ui.dialog() as loading_dialog:
        with ui.card().classes('p-6 items-center'):
            ui.label('Loading dataset...')
            ui.spinner(size='lg')
    loading_dialog.open()
    await ui.run_javascript('await new Promise(r => setTimeout(r, 0));')

    try:
        rows, run_grid_columns = await nicegui_run.io_bound(
            inspector.backend.get_runs_for_day,
            target_day=target_day,
            offset_hours=offset_hours,
        )
    except Exception as e:
        loading_dialog.close()
        ui.notify(f"Error loading run: {e}", type="negative", close_button="OK")
        ui.label(f"Failed to load runs for day ({target_day})!\n{e}")
        rows = []
        run_grid_columns = {}
    finally:
        if loading_dialog.visible:
            loading_dialog.close()

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


def open_run_page(run_id: int):
    app.storage.general["avg_axis"] = app.storage.tab["avg_axis_input"].value
    app.storage.general["result_keywords"] = app.storage.tab["result_keyword_input"].value
    ui.navigate.to(f'/run/{run_id}', new_tab=True)
