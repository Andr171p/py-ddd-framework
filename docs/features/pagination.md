# Пагинация и сортировка

Репозитории принимают `Pagination` и возвращают `Page[T]`: элементы и метаданные навигации живут вместе. DDF поддерживает две стратегии, выбираемые параметром `pagination`.

## Offset

Подходит для таблиц, где пользователю нужен номер страницы и общее число результатов.

```http
GET /users?pagination=offset&page=3&size=25
```

Ответ содержит `page`, `size`, `total`, `pages`, `has_next`, `has_prev`. Реализация выполняет `COUNT` и `LIMIT/OFFSET`.

Преимущество — переход к произвольной странице. Недостаток — большой `OFFSET` становится дорогим, а при изменении данных между запросами элементы могут сдвигаться.

## Cursor (keyset)

Подходит для ленты, экспорта и обхода больших наборов.

```http
GET /events?pagination=cursor&size=50
GET /events?pagination=cursor&size=50&cursor=eyJmaWVsZCI6ImlkIiwuLi59
```

Курсор непрозрачен для клиента: он кодирует позицию последнего элемента, поле и направление сортировки. При этом реализация запрашивает `size + 1` строку, чтобы определить `has_next` без полного `COUNT`.

В SQLAlchemy-адаптере cursor доступен только для `id`, `created_at`, `updated_at`; это стабильные и индексируемые поля. Для неуникальной даты к сортировке добавляется `id` как tie-breaker, поэтому элементы не повторяются на границе страницы.

!!! note "UUIDv7 полезен не только как ID"

    UUIDv7 упорядочиваем по времени создания, поэтому он работает естественным курсором по умолчанию. Это не отменяет отдельного индекса и не заменяет `created_at`, если бизнесу нужна именно дата.

## FastAPI dependency

`PaginationQuery` можно использовать как dependency:

```python
from fastapi import APIRouter, Depends
from ddf.application.dtos import PaginationQuery

router = APIRouter()

@router.get("/users")
async def list_users(pagination: PaginationQuery):
    return await users.find(pagination)
```

По умолчанию dependency использует `offset`, `page=1`, `size=50`; максимальный размер — 100. Модели DTO сами по себе имеют default `size=10`, поэтому при создании `OffsetPagination()` вручную размер отличается от HTTP-default. Задавайте `size` явно в сервисном коде, где это существенно.

## Сортировка

`parse_sort_query_param()` понимает три формы: `name`, `-name`, `name:desc`.

```python
from ddf.application.dtos import parse_sort_query_param

sort = parse_sort_query_param("-created_at")
page = await users.find(pagination, sort=sort)
```

SQLAlchemy-адаптер проверяет наличие поля на ORM-модели, но не имеет отдельного whitelist для сортировки. Не передавайте пользовательскую строку напрямую: на HTTP-границе сопоставляйте допустимые публичные имена с разрешёнными ORM-полями.
