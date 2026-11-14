from pydantic import BaseModel, ConfigDict

from ddf.application.realtime import Event, Room


class RealtimeDelivery[T](BaseModel):
    model_config = ConfigDict(frozen=True)

    room: Room
    event: Event[T]
