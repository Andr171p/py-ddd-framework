from ddf.application.uow import UnitOfWork
from ddf.domain.models import Entity

from .event_store import EventStore
from .types import CollectedEvent, EventPublisher


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
        collected: list[CollectedEvent] = []

        for entity in entities:
            collected.extend((event, entity) for event in entity.collect_events())

        try:
            if self.event_store is not None and collected:
                await self.event_store.record_all(collected)

            await self._uow.commit()

        except Exception:
            await self._uow.rollback()
            raise

        if collected:
            await self._event_publisher([event for event, _ in collected])
