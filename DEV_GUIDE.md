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
run_session.py             # Per-tab RunSession (run, settings, widgets, plot grid), released on client delete
pages/
  greeter.py               # Route: /         — DB connection dialog (QCoDeS file picker or Arbok credentials)
  database_browser.py      # Route: /browser  — Day selector + run grid, double-click opens run
  run_view.py              # Route: /run/{id}  — Full run view: dimension controls, plots, metadata
widgets/
  day_selector.py          # AG Grid for day selection, calls inspector.backend.get_days()
  run_selector.py          # AG Grid for runs on selected day, calls inspector.backend.get_runs_for_day()
  build_xarray_grid.py     # PlotGrid: schedules renders, computes in a worker thread, updates plots in place
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
  view_state.py            # Immutable snapshot of dim roles + plot options, handed to the worker thread
analysis/
  analysis_base.py         # Minimal base class for analysis extensions
  prepare_data.py          # Data averaging (xarray .mean()), histogram binning, FFT, decay spectrum
helpers/
  figure_builder.py        # Pure Plotly figure dicts (numpy arrays, no go.Figure), thread-safe
  render_scheduler.py      # One render at a time, "latest request wins" coalescing
  string_formaters.py      # Plot title and axis label formatting
  unit_formater.py         # SI prefix formatting (G, M, k, m, µ, n)
configurations/
  1d_plot.json             # Plotly template: scatter with lines+markers
  2d_plot.json             # Plotly template: heatmap with magma colorscale
tests/
  conftest.py              # Fixtures: ConcreteRun (DB-free BaseRun), 1D/2D/3D/4D xarray datasets
  test_dim.py              # Dim data class tests
  test_base_run.py         # Dimension assignment, fallbacks, keyword selection, subsetting, caching
  test_database_backend.py # QcodesBackend tested against a temp SQLite DB
  test_figure_builder.py   # Figure dicts, serialization, downsampling, log/gridline options
  test_render_scheduler.py # Coalescing, no concurrent renders, reload merging
  test_run_view_ui.py      # Real run page via NiceGUI's simulated user (slider bursts, reload, cleanup)
  test_qcodes_run.py       # QcodesRun + run page against a real temporary QCoDeS database
  test_performance.py      # Large synthetic dataset: cache hits, payload caps (marker: benchmark)
```

## Data Flow

1. **Connect** → `inspector.connect_to_*_database()` sets up connections and creates `inspector.backend`
2. **Browse** → `inspector.backend.get_days()` → user picks day → `inspector.backend.get_runs_for_day()`
3. **Open run** → New tab, `BaseRun.prepare_run()` loads xarray Dataset, infers dimensions
4. **Plot** → UI events call `request_plot_update()` → the tab's `PlotGrid` renders (see Rendering Pipeline)

## State Management

| Scope | Location | Contents |
|-------|----------|----------|
| App-wide | `state.inspector` (singleton) | DB connections, `backend`, paths, filesystem |
| Cross-tab | `app.storage.general` | Plot JSON configs, timezone, keywords |
| Per-tab (run view) | `RunSession` via `get_session()` | Run, `settings` (font, log scales, plot JSON), dim_widgets, plot grid |
| Per-tab (browser page) | `app.storage.tab` | Day/run grids, input refs |
| Per-dimension | `Dim` (pure data) in `run.sweep_dict` | Role assignment (`option`), `select_index` |
| Per-dimension UI | `DimWidget` in `session.dim_widgets` | NiceGUI selector, slider, label refs |

The run view deliberately avoids `app.storage.tab`: it raises a `RuntimeError` while the
websocket is disconnected, and it is kept for 30 days (`max_tab_storage_age`) — together
with the full dataset. A `RunSession` is registered per client and released (renders
cancelled, run dropped) when NiceGUI deletes the client.

## Rendering Pipeline

All tabs share one asyncio event loop, so nothing heavy may run on it.

1. **Request**: UI handlers (slider, dropdowns, checkboxes, settings) call `request_plot_update()`.
   It returns immediately. `RenderScheduler` runs one render at a time; requests arriving
   meanwhile collapse into a single follow-up render with the newest state. A slider drag
   therefore never builds a backlog, and the last render always reflects the final position.
2. **Snapshot** (event loop): `run.snapshot_view()` → `ViewState`, plus `PlotSettings`
   (templates, font, log scales, title texts).
3. **Compute** (worker thread, `run.io_bound`): `compute_figures()` → `run.compute_subset(view)`
   → `build_figures()`. Only reads the snapshots, never the mutable `Dim`s.
4. **Apply** (event loop): if the number of figures and columns is unchanged, existing
   `ui.plotly` elements get `update_figure()` (`Plotly.react` in the browser); otherwise the
   grid is rebuilt. A spinner appears only if a render takes longer than 0.3 s.

Reloads (Update button, auto-reload timer) go through the same scheduler with `reload=True`,
so a reload never overlaps a render. The auto-reload timer awaits its render, so ticks
cannot pile up either.

**Caching** (`BaseRun._caches`): averaged, binned and FFT data are cached per variable, keyed
by the data version and the averaged dims (+ bins / FFT dim / representation). Assigning
`run.full_data_set` bumps the version. Only `plot_selection` variables are computed, so a
slider step only does `isel`, and an FFT range change only slices the cached FFT.

**Payload**: figures are plain dicts with C-contiguous numpy arrays (heatmap z as float32),
serialized by NiceGUI's orjson without `.tolist()` or `go.Figure` validation. Without
`go.Figure`, plotly.py names must be expanded explicitly — template names
(`"plotly_dark"`) and most colorscale names (`"magma"`); plotly.js silently falls back to
its defaults (light theme, RdBu) otherwise — which `resolve_template()` does. Heatmap axes
longer than `PlotSettings.max_heatmap_points` (1000) are stride-decimated for display; the
title then says "display downsampled". `layout.uirevision` keeps user zoom while only
slider positions change.

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
- `option`: one of `'average'`, `'select_value'`, `'x-axis'`, `'y-axis'`, `'fft'`, `'decay'`
- `select_index`: index for `select_value` mode

`DimWidget` (in `widgets/dim_widget.py`) wraps a `Dim` and owns the UI elements:
- `selector`: NiceGUI `Select` dropdown for the role
- `slider` / `select_label`: NiceGUI slider + value label for `select_value` mode
- `sync_selector_to_dim()`: pushes `dim.option` to the UI after programmatic changes

`BaseRun` never touches UI. It signals role changes via `_on_dim_changed(dim)` →
`run_view.py` syncs the matching `DimWidget`. After a dataset reload, `PlotGrid` calls its
`on_reloaded` callback on the event loop, which updates the slider max values.

## Histogram Mode

Histogram mode replaces simple averaging with binned distributions. When enabled (`run.show_histogram = True`), dimensions assigned to the `average` role are collapsed into histograms rather than means.

**Data flow:**
1. `run_view.py` toggle switches between `'Average'` and `'histogram'` modes
2. `run.compute_subset(view)` sees `view.show_histogram` and uses binned instead of averaged data
3. `BaseRun._binned_data()` calls `bin_over_axis()` for each selected variable (cached)
4. Result has original non-binned dims + a new `'Current'` dim (bin centers)

**How `bin_over_axis` works** (in `analysis/prepare_data.py`):
- Takes a DataArray and list of dimension names to bin over
- Arbok sentinel dimensions (names containing `'arbok'`) are trimmed (last value is padding)
- Bin axes are moved to the end and flattened into one sample axis
- Bin edges: `mean ± 3σ`, 51 bins by default (auto-computed from finite values)
- Vectorized histogram: arithmetic bin indices for uniform bins (`searchsorted` otherwise),
  out-of-range/NaN values go to an overflow slot, then one `np.bincount` over all rows
- Output: DataArray with dims `[*kept_dims, 'Current']`, where `'Current'` coords are bin centers

**Plot rendering:**
- Since histogram converts 1D results (after averaging) into 2D (sweep × bins), they are rendered as 2D heatmaps
- Exception: variables ending in `'diff'` or `'state'` are kept as 1D line plots (already processed)
- The y-axis label shows `'Current'` (bin centers in the original measurement units)

**Constraints:**
- Histogram mode is mutually exclusive with FFT mode
- Cannot assign a dimension as `y-axis` while histogram is active (histogram provides its own y-axis)
- Averaged and binned data have separate caches; toggling back and forth reuses both

## Decay Spectrum Mode

Assigning a dimension (typically time) the `'decay'` role replaces it by a `decay_time`
axis, in the same units, log-spaced from the sample spacing up to the measured window.
The brightest point is the dominant decay time; its value is roughly the decay amplitude.

`compute_decay_spectrum()` (in `analysis/prepare_data.py`) is a regularised inverse Laplace
transform: each trace is modelled as `offset + Σ g_j·exp(-(t - t0)/τ_j)` and solved for
`g_j ≥ 0` with `scipy.optimize.nnls` plus Tikhonov regularisation (`DECAY_REGULARIZATION`).
A plain Laplace transform would not work: for `A·e^(-t/τ)` it gives `A/(s + 1/τ)`, which
peaks at s = 0 regardless of τ.

- Rising traces are flipped, so decays and rises from/to any baseline give the same spectrum
- NaNs (incomplete runs) are dropped per trace; non-uniform and descending time axes work
- Multiple decays are resolved if well separated; with noise, decays ~4× apart come out ~10%
  off (inverse Laplace is ill-conditioned)
- **Oscillating decays are not supported** (not representable by real exponentials) — use FFT
- The range slider (indices into the decay-time axis) only slices the cached spectrum
- Mutually exclusive with FFT and histogram mode

## Key Patterns

- **Lazy loading**: Datasets load only when a run is opened, not at startup
- **Declarative plots**: Plotly config lives in JSON files, editable at runtime via JSON dialog
- **Multi-tab**: Each run opens in a new browser tab with isolated state
- **Caching**: per-variable caches in `BaseRun._caches`; `run.last_subset` holds the last plotted data (download)
- **Off-loop compute**: dataset loading, plot computation and NetCDF export run via `run.io_bound()`
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

UI tests (`test_run_view_ui.py`, `test_qcodes_run.py`) drive the real `run_page` with
`nicegui.testing.user_simulation` (needs `pytest-asyncio`). `ComputeProbe` can slow down
`compute_figures` to reproduce large-dataset behaviour.

⚠ `user_simulation` calls `app.reset()`, which deletes NiceGUI's storage directory.
`conftest.py` therefore sets `NICEGUI_STORAGE_PATH` to a temp dir before NiceGUI is
imported — keep that at the top of the file.

```bash
pytest -m "not benchmark"  # skip the large-dataset performance tests
pytest -s -m benchmark     # show timings
```

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
- Plot updates always go through `request_plot_update()` — never build plots synchronously in a handler
- Code running in the worker thread (`compute_subset`, `figure_builder`) must not touch UI, `app.storage` or mutable `Dim`s
- Dimension roles: `'x-axis'`, `'y-axis'`, `'average'`, `'select_value'` (defined in `AXIS_OPTIONS` in `dim.py`)
- `BaseRun` and `Dim` must stay free of NiceGUI imports — all UI belongs in `widgets/` and `pages/`
- `BaseRun.prepare_run()` takes `avg_axis` and `result_keywords` as explicit args (no `app.storage` access)
- SQLAlchemy models live in `classes/models.py`, not inline in run files
