from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from teilauto.output.json_out import print_json, to_jsonable


@dataclass(frozen=True)
class Inner:
    when: datetime


@dataclass(frozen=True)
class Outer:
    name: str
    inner: Inner
    tags: tuple[str, ...]
    where: Path


def test_to_jsonable_recurses():
    obj = Outer(
        name="x",
        inner=Inner(when=datetime(2026, 7, 12, tzinfo=timezone.utc)),
        tags=("a", "b"),
        where=Path("/tmp/x"),
    )
    assert to_jsonable(obj) == {
        "name": "x",
        "inner": {"when": "2026-07-12T00:00:00+00:00"},
        "tags": ["a", "b"],
        "where": str(Path("/tmp/x")),  # separator differs on Windows
    }


def test_print_json_single_document(capsys):
    print_json([{"a": 1}])
    out = capsys.readouterr().out
    assert json.loads(out) == [{"a": 1}]
