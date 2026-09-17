from ddf.application.uow import UnitOfWork
from ddf.domain.events import Event
from ddf.domain.models import Entity

from .event_store import EventStore
from .types import EventPublisher


class EventDispatcher:
    def __init__(
            self,
            uow: UnitOfWork,
            evnt_publisher: EventPublisher,
            event_store: EventStore | None = None,
    ) -> None:
        self._uow = uow
        self._event_publisher = evnt_publisher
        self.event_store = event_store

    async def __call__(self, *entities: Entity) -> None:
        events: list[Event] = []
        for entity in entities:
            events.extend(entity.collect_events())

        try:
            if self.event_store is not None and events:
                await self.event_store.record_all(events)

            await self._uow.commit()

        except Exception:
            await self._uow.rollback()
            raise

        if events:
            await self._event_publisher(events)
