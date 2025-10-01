from nicegui import ui

with ui.row().classes('w-full gap-4 items-start'):
    # LEFT: Select menus in a vertical column
    with ui.column().classes('w-1/3 gap-4'):
        ui.select(['Option A1', 'Option A2'], label='Select A')
        ui.select(['Yes', 'No'], label='Select B')
        ui.select(['Low', 'Medium', 'High'], label='Select C')

    # RIGHT: AGGrid in another column
    with ui.column().classes('w-2/3'):
        ui.aggrid({
            'columnDefs': [
                {'headerName': 'Name', 'field': 'name'},
                {'headerName': 'Age', 'field': 'age'},
            ],
            'rowData': [
                {'name': 'Alice', 'age': 30},
                {'name': 'Bob', 'age': 25},
            ],
        }).classes('w-full h-64')

ui.run()
