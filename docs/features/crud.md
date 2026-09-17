# CRUD-сервис

`Crud` собирает однообразный прикладной сценарий вокруг репозитория: загружает агрегат, вызывает доменный handler, сохраняет результат, коммитит и отдаёт response DTO. Это полезно для обычных административных ресурсов, где сценарии действительно похожи.

Не применяйте его для сложных процессов вроде оформления заказа с резервированием склада: явный use case будет понятнее.

## Точки расширения

| Точка | Назначение | Пример |
| --- | --- | --- |
| handler | доменное изменение | создать пользователя, сменить статус |
| wrapper | обёртка до/после base-операции | проверка доступа, аудит, tenancy |
| `to_response` | перевод доменной модели в DTO ответа | скрыть внутренние поля |

Для безопасности операция отключена, пока её handler не передан. Вызов, например, `create()` без `create_handler` выбросит `OperationNotAllowedError`, а не создаст полуготовую сущность.

## Пример

```python
from dataclasses import dataclass
from pydantic import BaseModel

from ddf.application.crud import Crud
from ddf.domain.models import Entity


@dataclass
class Label(Entity):
    name: str = ""


class CreateLabel(BaseModel):
    name: str


class LabelResponse(BaseModel):
    id: str
    name: str


async def create_label(dto: CreateLabel, _options: None) -> Label:
    return Label(name=dto.name.strip())


labels = Crud(
    repository=label_repository,
    dispatcher=dispatcher,
    to_response=lambda label: LabelResponse(id=str(label.id), name=label.name),
    create_handler=create_label,
)
```

Handler возвращает уже валидный агрегат. Не переносите в него сериализацию HTTP-ответа: это работа `to_response`.

## Wrapper: проверка доступа

```python
async def restrict_update(next_, label, dto, actor):
    if actor is None or not actor.can("labels:update"):
        raise PermissionError("Недостаточно прав")
    return await next_(label, dto, actor)
```

Wrapper получает базовую операцию как `next_` и обязан вызвать её ровно один раз, если не прерывает сценарий. Благодаря этому можно добавлять поперечные политики без наследования `Crud`.

!!! warning "Удаление — это ваш use case"

    Базовый `Crud.delete()` вызывает `delete_handler`, затем `repository.update()` и диспетчеризует событие. Поэтому handler должен изменить состояние агрегата (например, установить `deleted_at`), а не выполнять физическое удаление. Для физического `DELETE` напишите отдельный явный сценарий.
