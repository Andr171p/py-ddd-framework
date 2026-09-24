# За 15 минут

Ниже — маленький, но не игрушечный агрегат задачи. Он показывает ключевую границу: модель меняет себя сама, а доставка и хранение остаются снаружи.

## 1. Опишите доменную модель

```python
from dataclasses import dataclass
from datetime import UTC, datetime

from ddf.domain.events import Event
from ddf.domain.models import AggregateRoot


@dataclass(frozen=True)
class TaskCompleted(Event):
    event_type = "tasks.task-completed"
    task_id: str = ""


@dataclass
class Task(AggregateRoot):
    title: str = ""
    completed_at: datetime | None = None

    def complete(self) -> None:
        if self.completed_at is not None:
            return  # операция идемпотентна для данного сценария

        self.completed_at = datetime.now(UTC)
        self.register_event(TaskCompleted(task_id=str(self.id)))
```

`Task` хранит инвариант и фиксирует факт, важный для других частей системы. Он не вызывает брокер и не делает `commit`.

## 2. Сформируйте use case

```python
from uuid import UUID

from ddf.application.events import EventDispatcher
from ddf.application.repositories import Repository
from ddf.application.utils import get_or_raise_not_found


async def complete_task(
    task_id: UUID,
    repository: Repository[Task],
    dispatch: EventDispatcher,
) -> Task:
    task = await get_or_raise_not_found(repository.read, task_id, Task)
    task.complete()
    await repository.update(task)
    await dispatch(task)
    return task
```

Диспетчер собирает накопленные события, при наличии event store записывает их, делает `commit`, а затем передаёт события publisher-у. Подробнее — в [разделе о событиях](../concepts/events.md).

## 3. Подключите транспорт

```python
from fastapi import APIRouter, Depends
from uuid import UUID

router = APIRouter()


@router.post("/tasks/{task_id}/complete")
async def complete(task_id: UUID, service=Depends(get_complete_task_service)):
    task = await service(task_id)
    return {"id": str(task.id), "completedAt": task.completed_at}
```

`get_complete_task_service` — composition root: здесь приложение передаёт use case конкретные реализации репозитория, Unit of Work и publisher-а. HTTP-контроллеру не нужно знать об SQLAlchemy.

!!! warning "Порядок важен"

    Сначала измените агрегат, затем сохраните его и только после этого передавайте в `EventDispatcher`. `collect_events()` извлекает события из объекта, поэтому повторный вызов без нового `register_event()` ничего не опубликует.

Дальше: [сущности и Value Object](../concepts/entities.md), [репозитории и Unit of Work](../concepts/persistence.md).
