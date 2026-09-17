# Query DSL

DSL предназначен для построения сложных запросов выборки данных без привязки API к конкретной СУБД или ORM.

Основные возможности:

- фильтрация по полям;
- логические группы `$and` и `$or`;
- отрицание через `Negation`;
- полнотекстовый поиск;
- сортировка через query-параметр;
- комбинация всех условий в одном запросе.

DSL описывает **что нужно найти**, а инфраструктурный слой решает, **как выполнить запрос**. Для SQLAlchemy это означает компиляцию DSL в SQLAlchemy expressions.

## Формат запроса

Фильтр передаётся в `body` запроса.

Простейшее условие:

```json
{
  "filter": {
    "field": "status",
    "op": "$eq",
    "value": "open"
  }
}
```

Сортировка передаётся через query-параметр:

```http
GET /items?sort=-createdAt
```

Поддерживаются два формата:

```text
?sort=createdAt:desc
?sort=-createdAt
```

По умолчанию используется `asc`:

```text
?sort=createdAt
```

## Condition

`Condition` описывает условие для одного поля.

```json
{
  "field": "priority",
  "op": "$gte",
  "value": 3
}
```

### Операторы сравнения

| Оператор | Назначение | Пример |
|---|---|---|
| `$eq` | равно | `priority = 3` |
| `$ne` | не равно | `status != "closed"` |
| `$gt` | больше | `priority > 3` |
| `$gte` | больше или равно | `priority >= 3` |
| `$lt` | меньше | `priority < 3` |
| `$lte` | меньше или равно | `priority <= 3` |
| `$in` | входит в список | `status IN (...)` |
| `$nin` | не входит в список | `status NOT IN (...)` |
| `$like` | SQL `LIKE` | `title LIKE "%printer%"` |
| `$ilike` | регистронезависимый `LIKE` | `title ILIKE "%printer%"` |
| `$isNull` | значение `NULL` | `deletedAt IS NULL` |
| `$isNotNull` | значение не `NULL` | `deletedAt IS NOT NULL` |

Для `$in` и `$nin` значение должно быть списком:

```json
{
  "field": "status",
  "op": "$in",
  "value": ["open", "pending"]
}
```

Для `$isNull` и `$isNotNull` значение не требуется:

```json
{
  "field": "deletedAt",
  "op": "$isNull"
}
```

## Логические группы

`Group` объединяет несколько фильтров.

### `$and`

```json
{
  "filter": {
    "op": "$and",
    "filters": [
      {
        "field": "status",
        "op": "$eq",
        "value": "open"
      },
      {
        "field": "priority",
        "op": "$gte",
        "value": 3
      }
    ]
  }
}
```

Эквивалентно:

```text
status = 'open' AND priority >= 3
```

### `$or`

```json
{
  "filter": {
    "op": "$or",
    "filters": [
      {
        "field": "status",
        "op": "$eq",
        "value": "open"
      },
      {
        "field": "status",
        "op": "$eq",
        "value": "pending"
      }
    ]
  }
}
```

Эквивалентно:

```text
status = 'open' OR status = 'pending'
```

## Отрицание

`Negation` инвертирует условие или целую группу.

```json
{
  "filter": {
    "filter": {
      "field": "status",
      "op": "$eq",
      "value": "closed"
    }
  }
}
```

Логически:

```text
NOT status = 'closed'
```

На практике отрицание особенно полезно для сложных групп:

```json
{
  "filter": {
    "filter": {
      "op": "$or",
      "filters": [
        {
          "field": "status",
          "op": "$eq",
          "value": "closed"
        },
        {
          "field": "status",
          "op": "$eq",
          "value": "cancelled"
        }
      ]
    }
  }
}
```

Логически:

```text
NOT (status = 'closed' OR status = 'cancelled')
```

## Полнотекстовый поиск

Полнотекстовый поиск является отдельным видом фильтра и может комбинироваться с обычными условиями.

```json
{
  "filter": {
    "op": "$and",
    "filters": [
      {
        "field": "status",
        "op": "$eq",
        "value": "open"
      },
      {
        "query": "принтер не печатает"
      }
    ]
  }
}
```

Поисковые поля и способ поиска определяются backend-реализацией. Клиент не передаёт список физических колонок или индексов.

Это позволяет одной и той же форме запроса использовать разные реализации поиска, например PostgreSQL Full-Text Search или другую поисковую систему.

## Комбинированный пример

Сложный запрос может одновременно использовать фильтрацию, поиск и сортировку:

```http
GET /items?sort=-createdAt
```

```json
{
  "filter": {
    "op": "$and",
    "filters": [
      {
        "field": "status",
        "op": "$in",
        "value": ["open", "pending"]
      },
      {
        "field": "priority",
        "op": "$gte",
        "value": 3
      },
      {
        "op": "$or",
        "filters": [
          {
            "field": "assigneeId",
            "op": "$eq",
            "value": "550e8400-e29b-41d4-a716-446655440000"
          },
          {
            "query": "принтер"
          }
        ]
      }
    ]
  }
}
```

Логика запроса:

```text
(status IN ('open', 'pending'))
AND priority >= 3
AND (
    assignee_id = ...
    OR full_text_search('принтер')
)
ORDER BY created_at DESC
```

## Значения

DSL поддерживает следующие типы значений:

```text
UUID
AwareDatetime
Decimal
str
int
float
bool
null
```

Также поддерживаются коллекции этих значений.

Конкретная допустимость значения определяется полем. Например, UUID не следует передавать для числового поля только потому, что значение формально входит в `RichJsonValue`.

## Сортировка

Сортировка передаётся query-параметром `sort`.

```text
?sort=createdAt:desc
```

или короткая форма:

```text
?sort=-createdAt
```

Несколько полей можно передавать в нескольких параметрах:

```text
?sort=-createdAt&sort=priority
```

Порядок параметров задаёт приоритет сортировки.

На backend поле сортировки должно проверяться по разрешённому списку полей. Нельзя напрямую передавать имя произвольной колонки в `getattr()` модели.

## Field whitelist

Каждая модель, поддерживающая DSL, должна явно определить доступные поля.

Пример:

```python
fields = (
    "id",
    "status",
    "priority",
    "createdAt",
    "assigneeId",
)
```

Whitelist используется для фильтрации и сортировки одновременно.

API-имена могут отличаться от внутренних имён модели:

```text
createdAt  → created_at
assigneeId → assignee_id
```

Таким образом camelCase остаётся частью API-контракта и не распространяется внутрь persistence layer.

## Архитектура

DSL не должен зависеть от SQLAlchemy, PostgreSQL или другой инфраструктуры.

```text
HTTP request
    ↓
Application DSL
    ↓
Filter / Sort
    ↓
Repository
    ↓
Infrastructure compiler
    ↓
SQLAlchemy expression
    ↓
Database
```

Для SQLAlchemy compiler превращает:

```text
Condition
Group
Negation
Search
```

в соответствующие SQLAlchemy expressions.

## Ограничения и подводные камни

### 1. Не использовать `getattr()` для полей DSL

Нельзя делать:

```python
getattr(model, condition.field)
```

Имя поля приходит от клиента и должно проверяться через whitelist.

### 2. Не связывать Search с физическими колонками

Клиент передаёт:

```json
{"query": "принтер"}
```

но не:

```json
{"query": "принтер", "fields": ["title", "description"]}
```

Состав поискового индекса и его реализация являются ответственностью backend.

### 3. `$like` и полнотекстовый поиск — разные вещи

`$like` / `$ilike` предназначены для сопоставления значения конкретного поля.

`Search` предназначен для полнотекстового поиска и может использовать отдельный индекс.

### 4. Учитывать тип поля

`RichJsonValue` задаёт общий набор возможных значений, но не означает, что любое значение допустимо для любого поля.

Например:

```text
priority → number
createdAt → datetime
id → UUID
status → enum/string
```

Проверка совместимости поля и значения должна выполняться до построения SQL expression.

### 5. `$in` и `$nin` требуют коллекцию

Корректно:

```json
{
  "field": "status",
  "op": "$in",
  "value": ["open", "pending"]
}
```

Некорректно:

```json
{
  "field": "status",
  "op": "$in",
  "value": "open"
}
```

### 6. Пустые группы должны быть запрещены

Группа без условий:

```json
{
  "op": "$and",
  "filters": []
}
```

не несёт полезной семантики и должна отклоняться на этапе валидации.

### 7. `$isNull` и `$isNotNull` не используют `value`

Корректно:

```json
{
  "field": "deletedAt",
  "op": "$isNull"
}
```

### 8. Не добавлять оператор без необходимости

DSL должен расширяться только под реальные сценарии. Новый оператор должен иметь понятную семантику для всех поддерживаемых реализаций.

## Рекомендации для разработчиков

При добавлении нового поля в DSL сначала определите:

1. должно ли поле быть доступно для фильтрации;
2. должно ли оно быть доступно для сортировки;
3. должно ли оно участвовать в полнотекстовом поиске;
4. какие операторы допустимы для этого поля;
5. как значение приводится к типу модели.

Не следует считать, что наличие поля в ORM-модели автоматически делает его доступным через API.

DSL является API-контрактом, поэтому изменение поддерживаемых операторов, полей или их семантики требует обратной совместимости.