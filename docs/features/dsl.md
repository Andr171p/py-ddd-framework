# DSL фильтрации

DSL описывает фильтр как валидируемое дерево Pydantic, а не как SQL-строку из запроса пользователя. Это удобно для HTTP API, потому что один формат можно передать в SQLAlchemy и потенциально в другой backend.

## Узлы и операторы

| Узел | Смысл |
| --- | --- |
| `Condition` | сравнение поля со значением |
| `Group` | объединение дочерних фильтров через `$and` / `$or` |
| `Negation` | отрицание вложенного фильтра (`filter` в JSON) |
| `Search` | полнотекстовый поиск, предоставляемый адаптером |

Поддерживаемые сравнения: `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$nin`, `$like`, `$ilike`, `$isNull`, `$isNotNull`.

```json
{
  "op": "$and",
  "filters": [
    {"field": "status", "op": "$eq", "value": "active"},
    {"field": "createdAt", "op": "$gte", "value": "2026-01-01T00:00:00Z"}
  ]
}
```

В Python это та же структура:

```python
from ddf.application.dsl import Condition, Group

filter_ = Group(
    op="$and",
    filters=(
        Condition(field="status", op="$eq", value="active"),
        Condition(field="createdAt", op="$gte", value="2026-01-01T00:00:00Z"),
    ),
)
```

## SQLAlchemy и whitelist

`SqlAlchemyRepository.filter_whitelist` — обязательная граница API. В неё включают *имена, разрешённые внешнему клиенту*, а не все колонки таблицы.

```python
class UserRepository(SqlAlchemyRepository[User, UserRow]):
    model = UserRow
    data_mapper = UserMapper()
    filter_whitelist = ("email", "status", "createdAt")
```

Компилятор переводит camelCase API (`createdAt`) в snake_case ORM (`created_at`) и не даёт обращаться к полям вне списка. Это одновременно контракт API и защита от раскрытия внутренних атрибутов.

`$in` и `$nin` требуют список; `$like` и `$ilike` — строку. Для `Search` передайте в репозиторий `search` — функцию, которая строит выражение SQLAlchemy для конкретной базы.

!!! warning "Текущая реализация групп"

    В версии 0.1.0 рекурсивная компиляция `Group`/`Negation` в `ddf.infra.database.sqlalchemy.filters` требует исправления сигнатур вызовов. Простое атомарное `Condition` поддерживается; вложенные группы и отрицания не следует включать в публичный API до покрытия интеграционными тестами. Формат DSL и whitelist можно проектировать уже сейчас.

## Не превращайте DSL в язык запросов к БД

- Не принимайте произвольное имя поля и произвольную сортировку.
- Ограничьте глубину/число фильтров на HTTP-границе, чтобы избежать очень больших выражений.
- Преобразуйте ошибки `ValueError` в понятный клиенту HTTP 422/400, не отдавая текст SQLAlchemy.
- Для сложных аналитических выборок создайте отдельный endpoint и оптимизированный read model.
