"""
Output rendering: table, json, error, confirm.
Inputs: columns/rows for tables, any dict for JSON.
Outputs: terminal output via rich or typer.
Failure modes: respects NO_COLOR env via rich defaults.
"""
from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console
from rich.table import Table


_console = Console()
_err_console = Console(stderr=True)


def print_table(columns: list[str], rows: list[tuple[str, ...]]) -> None:
    table = Table(*columns, show_header=True, header_style="bold")
    for row in rows:
        table.add_row(*row)
    _console.print(table)


def print_json(data: Any) -> None:
    _console.print_json(json.dumps(data))


def print_err(msg: str) -> None:
    _err_console.print(f"[red]Error:[/red] {msg}", highlight=False)


def confirm(prompt: str) -> bool:
    return typer.confirm(prompt)
