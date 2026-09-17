from datetime import UTC, datetime

from .models import Entity


def apply_changes[EntityT: Entity](entity: EntityT, **changes) -> EntityT:
    """
    Применяет переданные изменения к сущности.

    Значения ``None`` игнорируются.

    Если хотя бы одно значение изменилось, ``updated_at``
    сущности обновляется.

    Raises:
        AttributeError: Если у сущности отсутствует указанный атрибут.
    """

    changed = False

    for field_name, value in changes.items():
        if value is None:
            continue

        current = getattr(entity, field_name)
        if current == value:
            continue

        setattr(entity, field_name, value)
        changed = True

    if changed:
        entity.updated_at = datetime.now(UTC)

    return entity
