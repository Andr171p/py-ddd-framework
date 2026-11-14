from typing import Any

import json
from dataclasses import dataclass
from pathlib import Path

from .dataset import load_tickets

DATA = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True, slots=True)
class SearchCase:
    name: str
    expression: dict[str, Any]
    codes: frozenset[str]


@dataclass(frozen=True, slots=True)
class NullCase:
    name: str
    expression: dict[str, Any]
    postgres: frozenset[str]
    mongo: frozenset[str]


def load_shared_cases() -> tuple[SearchCase, ...]:
    return tuple(_search_case(item) for item in _read("shared_cases.json"))


def load_null_cases() -> tuple[NullCase, ...]:
    cases = tuple(
        NullCase(
            name=item["name"],
            expression=item["expression"],
            postgres=frozenset(item["postgres"]),
            mongo=frozenset(item["mongo"]),
        )
        for item in _read("null_cases.json")
    )
    _check_codes(*(case.postgres | case.mongo for case in cases))
    return cases


def require_case(name: str) -> SearchCase:
    for case in load_shared_cases():
        if case.name == name:
            return case
    raise KeyError(name)


def _search_case(item: dict[str, Any]) -> SearchCase:
    case = SearchCase(name=item["name"], expression=item["expression"], codes=frozenset(item["codes"]))
    _check_codes(case.codes)
    return case


def _check_codes(*groups: frozenset[str]) -> None:
    known = {ticket.code for ticket in load_tickets()}
    unknown = set().union(*groups) - known
    if unknown:
        raise ValueError(f"Unknown ticket codes: {sorted(unknown)}.")


def _read(name: str) -> list[dict[str, Any]]:
    return json.loads((DATA / name).read_text(encoding="utf-8"))
