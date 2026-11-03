"""Per-tab state of a run view, owned by the NiceGUI client that displays it."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any

from dataclasses import dataclass, field

from nicegui import context

if TYPE_CHECKING:
    from nicegui import Client
    from arbok_inspector.classes.base_run import BaseRun
    from arbok_inspector.widgets.build_xarray_grid import PlotGrid
    from arbok_inspector.widgets.dim_widget import DimWidget


@dataclass
class RunSession:
    """
    Everything one run-view tab holds: the run (dataset and caches), UI
    references and the tab-local plot settings.

    Sessions live in a registry keyed by client id instead of `app.storage.tab`:
    - they stay accessible while the websocket is briefly disconnected, whereas
      `app.storage.tab` raises a RuntimeError then;
    - they are released as soon as NiceGUI deletes the client, whereas tab
      storage (and with it the full dataset) is kept for 30 days.
    """
    run: BaseRun
    settings: dict[str, Any] = field(default_factory=dict)
    dim_widgets: dict[str, DimWidget] = field(default_factory=dict)
    plot_grid: PlotGrid | None = None


_sessions: dict[str, RunSession] = {}


def register_session(session: RunSession, client: Client | None = None) -> None:
    """Attach the session to the client; it is released when the client is deleted."""
    client = client or context.client
    client_id = client.id
    _sessions[client_id] = session
    client.on_delete(lambda: release_session(client_id))


def get_session(client: Client | None = None) -> RunSession | None:
    """Session of the given (default: current) client, None if released."""
    client = client or context.client
    return _sessions.get(client.id)


def release_session(client_id: str) -> None:
    """Stop rendering and drop all references to the run of a client."""
    session = _sessions.pop(client_id, None)
    if session is not None and session.plot_grid is not None:
        session.plot_grid.close()
