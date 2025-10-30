arbok_inspector is a small inspection and visualization utility for measurement
databases used alongside the Arbok/ekans measurement tooling.
It provides a lightweight GUI and CLI to browse runs and visualize data.
# arbok_inspector 🚀

Welcome! arbok_inspector is a small, friendly tool for exploring and visualizing measurement databases produced alongside the Arbok / ekans tooling. If you want to quickly peek at runs, inspect metadata, or try small analyses, this project helps you do that with a lightweight UI and some handy helpers. 🔍

Why you might use it
- Fast browsing of measurement runs and their metadata
- Interactive pages and widgets built with NiceGUI (see `pages/` and `widgets/`)
- Simple analysis and data preparation helpers in `analysis/`
- A bundled `test.db` for quick local demos

Quick start — Try it now (1–2 minutes)

1. From the project root (the folder containing `pyproject.toml`), install in editable/dev mode:

```bash
python -m pip install -e .
```

2. Launch the app (pick one):

```bash
python -m arbok_inspector.main
# or
python arbok_inspector/main.py
```

If the app asks for a database, point it at the included `test.db` to explore instantly. If you prefer the CLI, check `arbok_inspector/cli.py` for options.

If something doesn't start, check that dependencies from `pyproject.toml` are installed and that you're running a compatible Python version.

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

