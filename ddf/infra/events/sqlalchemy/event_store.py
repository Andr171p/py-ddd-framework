from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from ddf.application.events import CollectedEvent, get_event_context, get_event_payload
from ddf.domain.events import Event
from ddf.domain.models import Entity

from .models import EventOrm


def _build_event_orm(event: Event, entity: Entity) -> EventOrm:
    correlation_id, meta = get_event_context()
    return EventOrm(
        event_id=event.event_id,
        event_type=event.event_type,
        version=event.version,
        occurred_on=event.occurred_on,
        entity_id=entity.id,
        entity_type=type(entity).__name__,
        correlation_id=correlation_id,
        meta=meta,
        payload=get_event_payload(event),
    )


class SqlAlchemyEventStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_all(self, events: Sequence[CollectedEvent]) -> None:
        models = [_build_event_orm(event, entity) for event, entity in events]
        self._session.add_all(models)
        await self._session.flush()
