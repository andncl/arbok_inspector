"""Module containing day selector grid generation and update functions"""
from nicegui import ui, app

from arbok_inspector.state import inspector
from arbok_inspector.widgets.run_selector import update_run_selector

DAY_GRID_COLUMN_DEFS = [
    {'headerName': 'Day', 'field': 'day'},
]

AGGRID_STYLE = 'height: 95%; min-height: 0;'


async def trigger_update_run_selector(day):
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
            type='cellClicked',
            handler=lambda event: trigger_update_run_selector(event.args["value"])
        )
    update_day_selector(day_grid)
    return day_grid


def update_day_selector(day_grid: ui.aggrid | None = None) -> None:
    """Update the day selector grid with available days from the database."""
    if day_grid is None:
        if 'day_grid' not in app.storage.tab:
            return
        day_grid: ui.aggrid = app.storage.tab['day_grid']
    offset_hours = app.storage.general["timezone"]
    rows = inspector.backend.get_days(offset_hours)

    day_grid.clear()
    row_data = []
    for day, _ in rows[::-1]:
        row_data.append({'day': day})
    if app.storage.tab["last_selected_day"] is None:
        app.storage.tab["last_selected_day"] = rows[-1][0]
    day_grid.options['rowData'] = row_data
    day_grid.update()
    ui.notify(
        'Day selector updated: \n'
        f'found {len(row_data)} days',
        type='positive',
        multi_line=True,
        classes='multi-line-notification',
        position='top-right'
    )
