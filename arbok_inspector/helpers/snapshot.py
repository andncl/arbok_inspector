"""Flatten a QCoDeS station snapshot into searchable parameter rows."""
from __future__ import annotations

from typing import Any

# Container keys of a QCoDeS snapshot that are not part of a parameter's name
STRUCTURAL_KEYS = {"station", "instruments", "parameters", "submodules", "components", "channels"}
MAX_VALUE_LENGTH = 200


def flatten_snapshot(snapshot: dict | None) -> list[dict[str, str]]:
    """
    One row per parameter: {'name', 'value', 'unit'}, where the name is the
    parameter's `full_name` (e.g. 'dac_ch1') or its dotted path. Parameters are
    the dicts holding a 'value' together with parameter metadata.

    Args:
        snapshot: Parsed snapshot JSON, e.g. from `BaseRun.get_snapshot`
    """
    rows: list[dict[str, str]] = []

    def walk(node: Any, path: list[str]) -> None:
        if not isinstance(node, dict):
            return
        if "value" in node and ({"unit", "raw_value", "__class__"} & node.keys()):
            value = str(node["value"])
            if len(value) > MAX_VALUE_LENGTH:
                value = value[:MAX_VALUE_LENGTH] + "…"
            rows.append({
                "name": str(node.get("full_name") or ".".join(path)),
                "value": value,
                "unit": str(node.get("unit") or ""),
            })
            return
        for key, child in node.items():
            walk(child, path if key in STRUCTURAL_KEYS else path + [str(key)])

    walk(snapshot, [])
    return rows
