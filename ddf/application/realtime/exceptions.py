
class ConnectionClosedError(Exception):
    pass


class SlowConsumerError(Exception):
    """Клиент потребляет сообщения медленнее, чем сервер их публикует."""


class SubscriptionDeniedError(Exception):
    pass


class TooManySubscriptionsError(Exception):
    pass
