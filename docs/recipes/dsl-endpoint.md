# Рецепт: DSL в FastAPI endpoint

DSL лучше передавать в JSON-теле запроса. GET с вложенным JSON в query-параметре плохо читается, часто ломается в прокси и ограничен длиной URL. Для поиска используйте `POST /users/search` — это операция чтения, а не изменение ресурса.

```python
from fastapi import APIRouter, Depends, HTTPException

from ddf.application.dsl import Expression
from ddf.application.dtos import PaginationQuery, Sort, parse_sort_query_param

router = APIRouter()


@router.post("/users/search")
async def search_users(
    filter_: Expression,
    pagination: PaginationQuery,
    sort: str | None = None,
    repository: UserRepository = Depends(get_user_repository),
):
    try:
        parsed_sort: Sort | None = parse_sort_query_param(sort) if sort else None
        # Перед включением Group/Negation см. ограничение текущей версии DSL.
        return await repository.find(pagination, query=filter_, sort=parsed_sort)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Недопустимый фильтр или сортировка") from exc
```

Запрос:

```json
{
  "field": "status",
  "op": "$eq",
  "value": "active"
}
```

## Нормализуйте публичный контракт

Не делайте SQLAlchemy-поле контрактом endpoint. Например, клиент может знать `createdAt`, а репозиторий сопоставит его с `created_at`; оба разрешаются только через whitelist. Аналогично ограничьте публичные варианты `sort`:

```python
allowed_sort = {"createdAt": "created_at", "email": "email"}
if sort and sort.removeprefix("-").split(":", 1)[0] not in allowed_sort:
    raise HTTPException(status_code=422, detail="Сортировка по этому полю недоступна")
```

Преобразуйте ожидаемые ошибки в 422, добавьте лимит глубины JSON на gateway и покрывайте endpoint тестами для запрещённых полей, неправильного типа `$in` и пустой сортировки.
