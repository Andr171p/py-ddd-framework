from .entity import Entity


class AggregateRoot(Entity):
    """Корень агрегата - кластер доменных объектов,
    агрегат управляет их поведением и состоянием.
    """
