# arbok_inspector

arbok_inspector is a small inspection and visualization utility for measurement
databases used alongside the Arbok/ekans measurement tooling.
It provides a lightweight GUI and CLI to browse runs and visualize data.

## Highlights

- Browse measurement runs and metadata
- Interactive pages and widgets (NiceGUI-based UI components live in `pages/` and `widgets/`)
- Tools to prepare and analyze data in `analysis/`
- Includes a small test database (`test.db`) for local testing

## Quick start

1. Clone the repository and change into the `arbok_inspector` project directory (the folder that contains `pyproject.toml`).

2. Install the package in editable mode (this will install dependencies from `pyproject.toml`):

	 python -m pip install -e .

	 (Alternatively, use your preferred environment manager — see `pyproject.toml` for declared dependencies.)

3. Run the inspector application. There are a couple of ways to launch it:

	 - Run the package's main module:

		 python -m arbok_inspector.main

	 - Or run the module file directly:

		 python arbok_inspector/main.py

	 The project also contains a small CLI helper in `cli.py` — check it for available command-line options.

4. For a quick local demo, the repository includes `test.db` in the package directory. Point the inspector to that file when prompted or by using CLI options if available.

## Project layout

Key package files and directories (inside the `arbok_inspector/` package):

- `main.py` — application entrypoint and startup logic
- `cli.py` — command-line interface helpers
- `state.py` — application state management and database handling
- `pages/` — NiceGUI pages (UI screens such as the database browser and run view)
- `widgets/` — custom UI widgets and helpers used by the pages
- `analysis/` — analysis and data-preparation utilities
- `classes/` — small domain objects used by the app (e.g., run/dim helpers)
- `helpers/` — formatting and other small helper functions
- `test_main.py` — a small test that verifies basic behavior (run with pytest)

## License

See the repository `LICENSE` file in the project root for license details.

## Notes

- The exact runtime dependencies are declared in `pyproject.toml`; for reproducible installs prefer using that manifest and your environment manager of choice.
- If you need help running the app or want to add new visualizations, look at `pages/` and `widgets/` for examples of how UI components are composed.

