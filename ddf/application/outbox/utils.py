from ddf.application.events import serialize_event
from ddf.domain.models import Entity

from .message import OutboxMessage
from .outbox_store import OutboxStore


async def save_events_to_outbox(outbox: OutboxStore, *entities: Entity) -> None:
    """Переносит накопленные доменные события в outbox текущей транзакции."""

    messages = [
        OutboxMessage(
            id=event.event_id,
            type=event.event_type,
            occurred_on=event.occurred_on,
            payload=serialize_event(event),
        )
        for entity in entities
        for event in entity.collect_events()
    ]
    await outbox.save_all(messages)
