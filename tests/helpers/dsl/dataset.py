from typing import Any

import json
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from ddf.domain.models import Entity

DATA_PATH = Path(__file__).resolve().parent / "data" / "tickets.json"
INTERNAL_NOTE_PREFIX = "secret-"
CREATED_AT = datetime.fromisoformat("2026-01-01T00:00:00+00:00")


@dataclass(frozen=True, slots=True)
class TicketSeed:
    id: UUID
    code: str
    organization_id: str
    title: str
    status: str
    priority: int
    assignee_name: str | None
    urgent: bool
    due_at: datetime | None
    omit: frozenset[str]


@dataclass(kw_only=True)
class Ticket(Entity):
    code: str
    organization_id: str
    title: str
    status: str
    priority: int
    assignee_name: str | None
    urgent: bool
    due_at: datetime | None
    internal_note: str


def note_for(code: str) -> str:
    return f"{INTERNAL_NOTE_PREFIX}{code}"


def entity_from_seed(seed: TicketSeed) -> Ticket:
    return Ticket(
        id=seed.id,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
        deleted_at=None,
        code=seed.code,
        organization_id=seed.organization_id,
        title=seed.title,
        status=seed.status,
        priority=seed.priority,
        assignee_name=seed.assignee_name,
        urgent=seed.urgent,
        due_at=seed.due_at,
        internal_note=note_for(seed.code),
    )


@lru_cache(maxsize=1)
def load_tickets() -> tuple[TicketSeed, ...]:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    tickets = tuple(_seed(item) for item in payload)
    codes = [ticket.code for ticket in tickets]
    ids = [ticket.id for ticket in tickets]
    if len(codes) != len(set(codes)) or len(ids) != len(set(ids)):
        raise ValueError("Ticket codes and ids must be unique.")
    return tickets


def by_code(code: str) -> TicketSeed:
    for ticket in load_tickets():
        if ticket.code == code:
            return ticket
    raise KeyError(code)


def _seed(item: dict[str, Any]) -> TicketSeed:
    due_at = item["dueAt"]
    return TicketSeed(
        id=UUID(item["id"]),
        code=item["code"],
        organization_id=item["organizationId"],
        title=item["title"],
        status=item["status"],
        priority=item["priority"],
        assignee_name=item["assigneeName"],
        urgent=item["urgent"],
        due_at=None if due_at is None else datetime.fromisoformat(due_at),
        omit=frozenset(item.get("omit", ())),
    )
