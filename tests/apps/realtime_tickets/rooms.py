from ddf.application.realtime import Room, Subscription
from ddf.application.realtime.exceptions import SubscriptionDeniedError


def room_for(org_id: str, subscription: Subscription) -> Room:
    if subscription.topic != "ticket":
        raise SubscriptionDeniedError()
    return Room(f"org:{org_id}:ticket:{subscription.key}")


def make_resolver(org_id: str, *, deny: set[str] | None = None, delay: float = 0.0):
    blocked = deny or set()

    async def resolve(subscription: Subscription) -> Room:
        if delay > 0:
            import asyncio

            await asyncio.sleep(delay)

        if subscription.key in blocked:
            raise SubscriptionDeniedError()

        return room_for(org_id, subscription)

    return resolve
