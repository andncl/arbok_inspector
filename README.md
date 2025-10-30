# arbok_inspector 🐍
arbok_inspector is an browser based inspection and visualization utility for QCoDeS measurement
databases.
It provides a lightweight GUI and CLI to browse runs and visualize data. 

## Features 🔎
The most commonly used used tool to visualize QCoDeS databases is
[plottr](https://github.com/toolsforexperiments/plottr).
Plottr is a great tool to get started, but struggles with increasing abounts of data.

This is how arbok_inspector streamlines your data inspection:
- Fast browsing of measurement runs and their metadata
- Written in tailwind using nicegui wrapper
- Browser based approach ensures cross system compatibily
- Selected runs are opened in a new tab and run on a separate thread
  - this avoids blocking the entire application when loading big datasets
- plotting backend is plotly which natively returns html
  - plotly plot customization is declarative and can therefore be tweaked in a simple json editor without implementing each customization by hand
- runs are only loaded on demand
  - startup time in plottr can be several minutes for large databases
  - SQL queries load only the given days upon database selection, only loads respective runs once day is selected

## Quick start — Try it now (1–2 minutes) 📲

1. From the project root (the folder containing `pyproject.toml`), install :

```bash
python -m pip install -e .
```
To be added to pypi (pip) soon!

2. Launch the app (pick one):

```bash
arbok-inspector
```

Alternatively run in editable/dev mode:
```bash
python -m arbok_inspector/dev.py
```

Project layout — what you'll find

- `main.py` — app entrypoint and startup logic
- `cli.py` — command-line helpers and quick-run options
- `state.py` — application state & database handling
- `pages/` — NiceGUI pages (database browser, run view, greeter, ...)
- `widgets/` — reusable UI widgets (grid builders, selectors, dialogs)
- `analysis/` — analysis and data-prep utilities
- `classes/` — small domain objects used across the app
- `helpers/` — formatting and utility helpers
- `test_main.py` — simple tests you can run with pytest

Development & testing 🛠️

- Run tests:

```bash
pytest -q
```

- Use an editable install for local development to pick up changes immediately:

```bash
python -m pip install -e .
```

Contributing & help 🙌

Contributions, bug reports, and small feature requests are welcome. If you want to add a visualization or a new page, use `pages/` and `widgets/` for examples of how UI components are composed. When opening a PR, please keep changes focused and include a short description of how to exercise the change locally.

License

See the `LICENSE` file in the project root for license details.

Notes & tips

- For exact runtime dependencies check `pyproject.toml` — prefer using that manifest (and a virtual environment) for reproducible installs.
- If you want me to add a short walkthrough for common tasks (open a run, plot data, export CSV), tell me which task you'd like first and I can add a step-by-step example here. 📘

