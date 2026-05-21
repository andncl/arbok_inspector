# Arbok Inspector - Developer Guide

## What is this?

A browser-based visualization tool for QCoDeS quantum measurement databases. Built with NiceGUI (Tailwind wrapper) + Plotly. Supports two backends: QCoDeS SQLite databases and native Arbok (PostgreSQL + MinIO/Zarr).

## Quick Start

```bash
uv sync                    # install deps (uv.lock included)
arbok-inspector            # production server on port 8090
arbok-inspector-dev        # dev server with hot reload
arbok-inspector --port N   # custom port
```

## Architecture

```
main.py                    # CLI entry, imports pages (auto-registers routes), launches NiceGUI
state.py                   # Global singleton `inspector` — holds DB connections, backend, app config
pages/
  greeter.py               # Route: /         — DB connection dialog (QCoDeS file picker or Arbok credentials)
  database_browser.py      # Route: /browser  — Day selector + run grid, double-click opens run
  run_view.py              # Route: /run/{id}  — Full run view: dimension controls, plots, metadata
widgets/
  day_selector.py          # AG Grid for day selection, calls inspector.backend.get_days()
  run_selector.py          # AG Grid for runs on selected day, calls inspector.backend.get_runs_for_day()
  build_xarray_grid.py     # Main plot orchestrator: subsets data, creates Plotly figures, renders grid
  build_run_view_actions.py# Action buttons: refresh, download, plot settings, layout controls
  json_plot_settings_dialog.py # Modal JSON editor for Plotly config
  build_xarray_html.py     # Renders xarray dataset HTML summary
  dim_widget.py            # UI binding layer for Dim — owns NiceGUI widget refs (selector, slider, label)
classes/
  database_backend.py      # DatabaseBackend ABC + QcodesBackend + NativeArbokBackend implementations
  models.py                # SQLAlchemy ORM models (SqlRun, SqlExperiment, SqlDevice)
  base_run.py              # Abstract base: dataset loading, dimension inference, subsetting, caching (no UI)
  qcodes_run.py            # QCoDeS run loader: SQLite + qcodes.dataset API
  native_run.py            # Native Arbok run loader: PostgreSQL (SQLAlchemy) + MinIO (fsspec/Zarr)
  dim.py                   # Pure data class: dimension name, role, select_index (no UI refs)
analysis/
  analysis_base.py         # Minimal base class for analysis extensions
  prepare_data.py          # Data averaging (xarray .mean()) and histogram binning (np.histogram)
helpers/
  string_formaters.py      # Plot title and axis label formatting
  unit_formater.py         # SI prefix formatting (G, M, k, m, µ, n)
configurations/
  1d_plot.json             # Plotly template: scatter with lines+markers
  2d_plot.json             # Plotly template: heatmap with magma colorscale
tests/
  conftest.py              # Fixtures: ConcreteRun (DB-free BaseRun), 1D/2D/3D/4D xarray datasets
  test_dim.py              # Dim data class tests
  test_base_run.py         # Dimension assignment, fallbacks, keyword selection, subsetting, callbacks
  test_database_backend.py # QcodesBackend tested against a temp SQLite DB
```

## Data Flow

1. **Connect** → `inspector.connect_to_*_database()` sets up connections and creates `inspector.backend`
2. **Browse** → `inspector.backend.get_days()` → user picks day → `inspector.backend.get_runs_for_day()`
3. **Open run** → New tab, `BaseRun.prepare_run()` loads xarray Dataset, infers dimensions
4. **Plot** → `build_xarray_grid()` subsets data per dimension selections, applies JSON templates, renders Plotly figures

## State Management

| Scope | Location | Contents |
|-------|----------|----------|
| App-wide | `state.inspector` (singleton) | DB connections, `backend`, paths, filesystem |
| Cross-tab | `app.storage.general` | Plot JSON configs, timezone, keywords |
| Per-tab | `app.storage.tab` | Current run, dim_widgets dict, local plot settings |
| Per-dimension | `Dim` (pure data) in `run.sweep_dict` | Role assignment (`option`), `select_index` |
| Per-dimension UI | `DimWidget` in `app.storage.tab["dim_widgets"]` | NiceGUI selector, slider, label refs |

## Database Backend Abstraction

`DatabaseBackend` (in `classes/database_backend.py`) is an ABC with two methods:
- `get_days(offset_hours)` → list of `(day_string, earliest_timestamp)` tuples
- `get_runs_for_day(target_day, offset_hours)` → `(row_dicts, column_defs)`

Concrete implementations:
- `QcodesBackend(db_path)` — raw SQLite queries
- `NativeArbokBackend(engine)` — SQLAlchemy text queries against PostgreSQL

The `inspector.backend` is set during connection and used by `day_selector.py` and `run_selector.py` — no more `if database_type == ...` branching in the widget layer.

## Dim / DimWidget Separation

`Dim` (in `classes/dim.py`) is a pure data class — no NiceGUI imports, fully testable:
- `name`: coordinate name
- `option`: one of `'average'`, `'select_value'`, `'x-axis'`, `'y-axis'`
- `select_index`: index for `select_value` mode

`DimWidget` (in `widgets/dim_widget.py`) wraps a `Dim` and owns the UI elements:
- `selector`: NiceGUI `Select` dropdown for the role
- `slider` / `select_label`: NiceGUI slider + value label for `select_value` mode
- `sync_selector_to_dim()`: pushes `dim.option` to the UI after programmatic changes

`BaseRun` never touches UI. It signals changes via two callbacks:
- `_on_dim_changed(dim)` → `run_view.py` syncs the matching `DimWidget`
- `_on_sliders_need_update()` → `run_view.py` updates slider max values

## Key Patterns

- **Lazy loading**: Datasets load only when a run is opened, not at startup
- **Declarative plots**: Plotly config lives in JSON files, editable at runtime via JSON dialog
- **Multi-tab**: Each run opens in a new browser tab with isolated state
- **Caching**: `last_avg_subset` / `last_avg_dict` avoid recomputation when only result selection changes
- **Async I/O**: Dataset loading uses `run.io_bound()` to avoid blocking the UI thread
- **Callback-driven UI sync**: `BaseRun` logic notifies the UI layer via callbacks, never imports NiceGUI
- **Backend polymorphism**: DB queries go through `inspector.backend` — adding a new DB type means one new class

## Database Backend Differences

| | QCoDeS | Native Arbok |
|--|--------|--------------|
| DB | SQLite (file) | PostgreSQL |
| Storage | Embedded in DB | MinIO (S3-compatible) via Zarr |
| Connection | `sqlite3` + raw SQL | SQLAlchemy engine |
| Dataset load | `qcodes.dataset.load_by_id().to_xarray_dataset()` | `xarray.open_zarr()` via fsspec |
| Type string | `'qcodes'` | `'native_arbok'` |

## Testing

```bash
pytest                     # run tests
pytest --cov               # with coverage
```

Tests use `ConcreteRun` (in `tests/conftest.py`), a DB-free `BaseRun` subclass that accepts an xarray Dataset directly. This lets all dimension logic, selection fallbacks, and subsetting be tested without any database or NiceGUI server.

`test_database_backend.py` tests `QcodesBackend` against a temporary SQLite database with realistic schema and data.

## Dependencies

- **nicegui ~3.6**: Web framework (wraps Tailwind, AG Grid, Quasar)
- **plotly ~6.5**: Plotting (generates HTML figures)
- **qcodes ~0.54**: QCoDeS measurement framework integration
- **xarray ~2026.1**: N-dimensional labeled data structures
- **sqlalchemy ~2.0**: Database ORM (native Arbok mode)
- **s3fs / minio**: S3-compatible storage access
- **zarr ~2.18**: Chunked array storage format

## Conventions

- Pages register routes via `@ui.page()` decorators — importing the module is enough
- Database-specific logic branches on `inspector.backend` (polymorphism), not `if/else` on type strings
- Plot updates always go through `build_xarray_grid()` — it clears and rebuilds the plot container
- Dimension roles: `'x-axis'`, `'y-axis'`, `'average'`, `'select_value'` (defined in `AXIS_OPTIONS` in `dim.py`)
- `BaseRun` and `Dim` must stay free of NiceGUI imports — all UI belongs in `widgets/` and `pages/`
- `BaseRun.prepare_run()` takes `avg_axis` and `result_keywords` as explicit args (no `app.storage` access)
- SQLAlchemy models live in `classes/models.py`, not inline in run files
