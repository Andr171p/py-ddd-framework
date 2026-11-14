from typing import Any

from datetime import datetime
from uuid import UUID

from pydantic import Field

from ddf.infra.database.mongo.mongo_base_model import MongoBaseModel
from ddf.infra.database.mongo.repository import MongoRepository

from .dataset import Ticket, TicketSeed, entity_from_seed, load_tickets

FILTER_FIELDS = {
    "id": "_id",
    "title": "title",
    "status": "status",
    "priority": "priority",
    "assigneeName": "assigneeName",
    "urgent": "urgent",
    "dueAt": "dueAt",
}


class TicketDocument(MongoBaseModel):
    __collection_name__ = "dsl_tickets"

    id: UUID = Field(alias="_id")
    code: str
    organization_id: str
    title: str
    status: str
    priority: int
    assignee_name: str | None = None
    urgent: bool
    due_at: datetime | None = None
    internal_note: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class TicketMapper:
    def to_model(self, entity: Ticket, /, **_kwargs: object) -> TicketDocument:
        return TicketDocument.model_validate(
            {
                "_id": entity.id,
                "code": entity.code,
                "organizationId": entity.organization_id,
                "title": entity.title,
                "status": entity.status,
                "priority": entity.priority,
                "assigneeName": entity.assignee_name,
                "urgent": entity.urgent,
                "dueAt": entity.due_at,
                "internalNote": entity.internal_note,
                "createdAt": entity.created_at,
                "updatedAt": entity.updated_at,
                "deletedAt": entity.deleted_at,
            }
        )

    def from_model(self, model: TicketDocument, /, **_kwargs: object) -> Ticket:
        return Ticket(
            id=model.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            code=model.code,
            organization_id=model.organization_id,
            title=model.title,
            status=model.status,
            priority=model.priority,
            assignee_name=model.assignee_name,
            urgent=model.urgent,
            due_at=model.due_at,
            internal_note=model.internal_note,
        )


class TicketRepository(MongoRepository[Ticket, TicketDocument]):
    model = TicketDocument
    data_mapper = TicketMapper()
    filter_whitelist = FILTER_FIELDS


def documents() -> list[dict[str, Any]]:
    mapper = TicketMapper()
    stored: list[dict[str, Any]] = []
    for seed in load_tickets():
        document = mapper.to_model(entity_from_seed(seed)).model_dump(by_alias=True)
        for field in seed.omit:
            document.pop(field, None)
        stored.append(document)
    return stored
