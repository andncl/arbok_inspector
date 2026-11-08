# arbok-inspector — changes since 1.4.0

## New features
- **Decay spectrum (`decay` role).** Turns a time axis into a decay-time axis in the same units. The brightest point is the dominant decay time, so you can read decay times without fitting. Works for decays and rises toward any baseline, and resolves multiple decays. Comes with a range slider like the FFT one. Oscillating decays aren't supported; use FFT for those.
- **Ridge readout.** Marks the brightest point of each row in FFT or decay heatmaps, and downloads the positions as CSV (e.g. decay time per voltage).
- **Copy as Python.** Generates notebook code that reproduces exactly the plotted data: averaging, slider positions, histogram, FFT or decay, and ranges.
- **Colour range.** Auto, 1–99 % percentile clipping, or manual z min/max (also works with log z).
- **Instrument snapshot.** Searchable table of every parameter value and unit stored with the run.
- **SVG export.** The plot toolbar's camera button saves SVG, or PNG at double resolution.
- **Plot JSON download.** Saves each plot as a plotly JSON file, including its data, titles and units. Easy to hand to an LLM or agent for further processing, and loads with `plotly.io.from_json`.

## Performance and stability
- **Responsive with large datasets.** Computation runs in the background, so one busy tab no longer freezes the others or drops their connection.
- **Smooth sliders.** Dragging no longer queues up stale updates; the plot always ends on the final position.
- **Much faster updates.** Results are cached, so slider steps and FFT/decay range changes don't recompute. Measured on 3 results × 8M points:
  - first render: 3.2 s → 0.3 s
  - slider step: 524 ms → 12 ms
- **3× faster histograms.**
- **Lighter browser load.** Plots update in place instead of being rebuilt, less data is sent to the browser, and very large heatmaps (over 1000 points per axis) are thinned for display, marked in the title.
- **Lower memory use.** A closed tab now frees its dataset straight away; before, it was kept in memory for up to 30 days.

## Improvements
- **Zoom is kept** while you move sliders.
- **Non-blocking loading spinner** instead of a modal dialog.
- **JSON editor:**
  - the `data` section is shown first
  - line style settings (`line`, `opacity`, …) now apply to all 1D traces
- **Font:** the default axis font size is now 15, and the Font field steps by 2.
- **Auto-reload** no longer shows a notification every cycle.

## Bug fixes
- Fixed errors and "Session expired" problems after loading large datasets.
- Fixed plots occasionally appearing twice.
- Fixed a crash in the "Selec." (selection) download.
- Fixed a crash when the number of plot columns was set to 0, and when the reload interval field was cleared.
- Selecting a parallel coordinate (alternative axis name) for a slider now works.

## For developers
- **New dependency:** `scipy~=1.17`. New dev dependency: `pytest-asyncio~=1.4`.
- **API changes:**
  - `build_xarray_grid()` is replaced by `request_plot_update()`
  - `BaseRun.set_on_sliders_need_update()` was removed
  - `QcodesRun` takes an optional `db_path` argument
- The run view keeps its state in a per-tab `RunSession` instead of `app.storage.tab`.
- The test suite grew from 156 to 333 tests, including end-to-end UI tests and tests against a real QCoDeS database. See [DEV_GUIDE.md](DEV_GUIDE.md) for the new architecture.
