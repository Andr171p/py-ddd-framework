# Best practices

Эти правила помогают применять DDF как набор небольших primitives, а не как архитектуру ради архитектуры. Выбирайте практику, когда она уменьшает реальную сложность продукта.

## Границы и зависимости

| Слой | Делайте | Не делайте |
| --- | --- | --- |
| `domain` | Инварианты, поведение агрегатов, Value Object, бизнес-события | Импорты FastAPI, SQLAlchemy, Redis, HTTP и SDK провайдеров |
| `application` | Use case, координация портов, транзакционная граница, команды | SQL, ORM relationship и обработку HTTP |
| `infra` | Реализации Protocol, маппинг, клиенты, миграции, worker | Решения о скидке, статусе заказа или правах предметной области |
| `api` | Валидация transport DTO, авторизация, преобразование ошибок | Доступ к ORM из endpoint и дублирование бизнес-правил |

Организуйте код сначала по bounded context (`billing`, `catalog`, `identity`), затем по слоям внутри контекста. Не делайте один глобальный `domain/` для несвязанных частей монолита.

Держите composition root в bootstrap/dependency provider: там связываются `AsyncSession`, repository, cache, publisher и use case. Конструкторы use case должны принимать узкие Protocol или функции — это делает unit-тесты простыми и не требует тестовой БД.

## Доменная модель

- Агрегат — транзакционная граница, а не вся предметная область. Между агрегатами храните ID, а не ORM relationship.
- Добавляйте метод, когда изменение имеет правило: `invoice.pay()`, а не `invoice.paid = True` в трёх endpoint-ах.
- Делайте Value Object неизменяемыми и валидируйте их при создании.
- Доменное событие называйте в прошедшем времени и задавайте ему неизменный `event_type`.
- Не превращайте каждый объект в абстрактную фабрику/service. Простые `dataclass` и функции — норма.

## Хранение и чтение

- ORM row и доменная entity имеют разные задачи. Используйте Data Mapper, когда домен содержит Value Object, инварианты или должен жить вне session.
- Пусть Unit of Work владеет commit/rollback. Repository делает `flush` при необходимости, но не скрытый commit.
- Выбирайте cursor pagination для больших, часто изменяемых списков и лент; offset — когда клиенту нужны номера страниц и total.
- Для cursor используйте только стабильные, индексируемые сортировки. DDF поддерживает `id`, `created_at`, `updated_at`; у timestamp всегда есть UUIDv7 tie-breaker.
- Разрешайте поля фильтра и сортировки явно через whitelist. Публичные имена API не обязаны совпадать с названиями колонок.

## Кэш

- Начинайте с cache-aside для `read(id)`, где key содержит bounded context и тип: `billing:invoice:{id}`.
- После update/delete инвалидируйте ключ; не считайте кэш источником истины для лимитов, остатков и других строгих проверок.
- Не кэшируйте произвольные списки до измерения hit ratio и определения ключа, включающего filter, sort, tenant и права.
- Учитывайте сериализацию. In-memory cache хранит ссылки на объект и хорош для тестов/одного процесса; Redis требует serializer и совместимой схемы.

## События и интеграции

- Сохраняйте агрегат до вызова `EventDispatcher`; dispatcher публикует только после commit.
- Используйте Event Store для аудита, а не как готовый event sourcing. Не дублируйте envelope в payload.
- Для критичной внешней доставки пишите transactional outbox в той же транзакции. Consumer проектируйте идемпотентным, допускающим reorder и повтор.
- Мониторьте pending rows, возраст старейшей строки, число retries и terminal `failed` сообщений. Настройте отдельный процесс разбора failed/DLQ, а не бесконечные попытки.
- Не включайте outbox parallelism, если потребитель зависит от порядка сообщений одного агрегата.

## AI

- Размещайте prompt/use case в `application`, правила допустимости результата — в `domain`, SDK clients и catalog моделей — в `infra/ai`.
- Маршрутизируйте сначала по hard constraints, затем выбирайте стоимость/скорость/качество policy. Всегда ставьте последнюю deterministic fallback strategy.
- Не записывайте prompt и output в логи/telemetry по умолчанию. Введите redaction, retention и явное согласование доступа до захвата содержимого.
- Не создавайте универсальный LLM/retriever/agent abstraction до повторяемого use case. `RoutedOpenAI` уже оставляет provider response нативным.

## Проверка качества

- Unit-тестируйте правила агрегата без сети и базы.
- Контрактно тестируйте каждый repository/store adapter: mapper round-trip, pagination, whitelist, commit/rollback, locking и retry.
- Проверяйте Event Store и outbox на rollback, duplicate delivery, restart worker-а и неизвестный `event_type`.
- Для AI пишите routing tests как таблицу: capabilities, modalities, context, цена, fallback и отсутствие подходящей модели.
- Собирайте документацию в CI: `uv run --group docs mkdocs build --strict`.

!!! tip "Критерий новой abstraction"

    Добавляйте framework abstraction только когда повторяется production-паттерн и новый API сокращает код приложения. Гипотетическая расширяемость не должна ухудшать корректность и ясность текущего решения.
