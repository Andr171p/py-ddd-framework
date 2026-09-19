from typing import Any

from dataclasses import asdict

from ddf.application.outbox import OutboxMessage

from .models import OutboxMessageOrm


def from_model(orm: OutboxMessageOrm) -> OutboxMessage:
    return OutboxMessage(
        id=orm.id,
        type=orm.type_,
        occurred_on=orm.occurred_on,
        payload=orm.payload,
        meta=orm.meta,
        attempts=orm.attempts,
        available_at=orm.available_at,
        processed_at=orm.processed_at,
        failed_at=orm.failed_at,
        last_error=orm.last_error,
    )


def to_values(message: OutboxMessage) -> dict[str, Any]:
    message_dict = asdict(message)
    message_dict["payload"] = dict(message.payload)
    message_dict["meta"] = dict(message.meta)
    return message_dict
