# Реестр решений DDF-A01…A40

В репозитории уже есть неизменяемые исторические ADR [0001–0004](index.md). Приложенный архитектурный материал использует такую же нумерацию для другого, более широкого набора решений. Чтобы не переписывать историю и не создать два значения одного ADR-номера, он оформлен здесь как тематический реестр **DDF-A01…A40**.

Статус отражает код на момент документации: **реализовано** — есть API/адаптер, **принцип** — ограничение развития, **roadmap** — решение принято, но API пока нет. Это намеренно отличает обещание от доступной возможности.

## Архитектурная основа и persistence

| ID | Решение | Статус |
| --- | --- | --- |
| A01 | DDD primitives и specialised capabilities разделены | Реализовано |
| A02 | SQLAlchemy `Base` отдельно от `EntityMixin` | Реализовано |
| A03 | Offset и cursor pagination; без отдельной time-series abstraction | Реализовано |
| A04 | Domain event и persisted event — разные представления | Реализовано |
| A05 | Event Store служит audit, а не Event Sourcing | Реализовано частично |
| A06 | Связь event/entity — `tuple`, без wrapper-классов | Реализовано |
| A07 | Общий execution context на `ContextVar` | Реализовано |
| A08 | Generic Event Store не навязывает tenant/actor columns | Реализовано |

### DDF-A01. Границы framework packages

**Проблема.** Базовые DDD primitives требуют ясных слоёв, но крупная AI-функциональность одновременно включает routing, OpenAI integration и content concerns. Раскладывать её по `application/ai` и `infra/ai` внутри самого framework означало бы искусственно разорвать capability.

**Решение.** Базовые primitives находятся в `ddf.domain`, `ddf.application`, `ddf.infra`; AI — отдельный top-level `ddf.ai`. Это capability framework, не новый слой приложения.

**Применение.** В проекте-потребителе AI use case остаётся в `application`, provider clients — в `infra/ai`, а бизнес-правила — в `domain`. Подробнее — в [структуре проекта](../getting-started/project-structure.md).

### DDF-A02. Base и EntityMixin

**Проблема.** Event Store и Outbox имеют собственный lifecycle и не являются обычными soft-deletable entities.

**Решение.** `Base(AsyncAttrs, DeclarativeBase)` даёт только declarative root. `EntityMixin` добавляет id/timestamps/deleted_at лишь обычным persistent entity. UUIDv7 передаётся как callable `default=uuid.uuid7`, а не результат вызова.

**Применение.** Не добавляйте mixin таблицам `stored_events`/`outbox_messages`. UUIDv7 подходит как sortable identifier и tie-breaker, но не как строгая глобальная позиция.

### DDF-A03. Две модели пагинации

**Проблема.** Offset удобен для UI, но нестабилен/дорог на больших изменяемых выборках. Time-series — сочетание range filter и cursor, не третий механизм.

**Решение.** Поддерживать offset и cursor/keyset. Cursor ограничен `id`, `created_at`, `updated_at`; для timestamp payload содержит `(timestamp, id)`, для UUIDv7 `id` — только id.

**Применение.** Offset берите для page/total UI, cursor — для лент и экспортов. Сортировка должна быть стабильной и индексируемой; arbitrary cursor sorting пока не поддерживается.

### DDF-A04–A08. Event audit и сквозной context

**Проблема.** Business event — immutable fact, а БД нуждается в audit envelope, entity association и технической метаинформации. При этом Event Store не должен диктовать IAM/multi-tenancy.

**Решение.** Event Store хранит `event_id`, `event_type`, `version`, `occurred_on`, `recorded_at`, entity fields, `correlation_id`, `meta` и custom payload раздельно. Пара event/entity — `tuple[Event, Entity]`; type entity — `type(entity).__name__`. Общий `ContextVar` содержит application-defined keys и используется также logging/tracing/outbox.

**Последствия.** Current state остаётся в обычных таблицах: без replay, snapshots, projections и global stream position. `EventStore.record_all()` реализован, read API ещё нет. Не храните FastAPI `Request`/session в context и не добавляйте framework-level `tenant_id`/`actor_id`: используйте `meta`.

## Transactional messaging

| ID | Решение | Статус |
| --- | --- | --- |
| A09 | Outbox — application primitive с infra adapters | Реализовано |
| A10 | `OutboxStore.save_all()` объединяет insert и update state | Реализовано |
| A11 | Статус outbox вычисляется по timestamps | Реализовано |
| A12 | Batch захватывается через `FOR UPDATE SKIP LOCKED` | Реализовано |
| A13 | Partial index содержит только pending rows | Реализовано |
| A14 | Processor обрабатывает ровно один batch | Реализовано |
| A15 | Worker — infrastructure/runtime; runner отдельно | Реализовано |
| A16 | Polling работает в drain mode | Реализовано |
| A17 | LISTEN/NOTIFY — wake-up, polling остаётся fallback | Реализовано |
| A18 | Inbox нужен только для idempotent incoming processing | Roadmap |
| A19 | Документация — часть feature completeness | Принцип |

### DDF-A09. Transactional Outbox

**Проблема.** Commit-then-publish даёт окно потери между БД и broker; application не должна зависеть от конкретного transport.

**Решение.** Application задаёт `OutboxMessage`, `OutboxStore`, `OutboxProcessor`, `OutboxConfig`; infrastructure — SQLAlchemy store, polling/LISTEN workers и broker publisher. Семантика — at-least-once, не exactly-once.

**Применение.** Записывайте domain change и outbox row в одну транзакцию, делайте consumer идемпотентным и наблюдайте retries/failed rows. Схема и ограничение текущего Event-адаптера — в [руководстве Outbox](../features/outbox.md).

### DDF-A10–A13. Сохранение, статус и конкурентность

**Проблема.** Отдельные insert/update методы усложняют processor; status дублирует timestamps; несколько workers не должны захватить одну строку.

**Решение.** `save_all()` делает PostgreSQL upsert и при conflict меняет лишь `attempts`, `available_at`, `processed_at`, `failed_at`, `last_error`. Статус выводится из timestamps. `acquire()` сортирует `(available_at, id)`, использует `FOR UPDATE SKIP LOCKED`; partial index покрывает pending set.

**Последствия.** Несколько workers обходятся без distributed lock. Row lock удерживается во время publish — разумный простой старт; при реальной высокой нагрузке понадобится lease/claim lifecycle.

### DDF-A14–A17. Processor и workers

**Проблема.** Scheduling в application-коде мешает тестированию; polling теряет throughput на backlog; NOTIFY ненадёжен как transport при disconnect.

**Решение.** Processor делает один `acquire → publish → save → commit`, worker определяет когда запускать, runner — где жить. Poller спит только при пустом batch. Notify worker делает LISTEN, затем проверяет outbox и ждёт notification с polling timeout.

**Применение.** TaskIQ/systemd/Kubernetes — runner, не worker strategy. Параллельная публикация отключена default-ом и не должна включаться, если важен порядок.

### DDF-A18. Inbox (roadmap)

**Проблема.** Входящие broker messages могут дублироваться, но им не нужен сложный lifecycle outbox.

**Решение.** Планируется минимальный `InboxStore.register(message) -> bool` через `INSERT … ON CONFLICT DO NOTHING`; registration и business change будут одной транзакцией. Повторы — ответственность broker consumer.

**Последствие.** В текущем репозитории нет Inbox API/таблицы/worker-а: не документируйте это как доступную функцию.

### DDF-A19. Feature complete включает документы

**Решение.** Значимая feature завершается implementation, tests, docstrings, feature guide, usage example и при необходимости ADR. Структура `docs/` разделяет getting started, concepts, features, integrations/recipes, reference, decisions и contributing.

**Применение.** README остаётся landing page, а MkDocs/Material — документация пользователя. Собирайте сайт strict mode в CI и явно помечайте roadmap.

## AI capability

| ID | Решение | Статус |
| --- | --- | --- |
| A20 | AI — optional capability | Реализовано |
| A21 | Нет собственного universal LLM abstraction | Принцип |
| A22 | RoutedOpenAI использует composition | Реализовано |
| A23 | `ModelSpec` — декларативный catalog, не persistence layer | Реализовано* |
| A24 | Routing policy не хранится в `ModelSpec` | Реализовано |
| A25 | Hard constraints до selection strategies | Реализовано |
| A26 | Strategies — ordered pipeline | Реализовано |
| A27 | Static priority — strategy | Реализовано |
| A28 | Generic score вместо множества strategy classes | Реализовано |
| A29 | Semantic routing optional и может отказаться | Реализовано |
| A30 | Анализировать OpenAI request структурно и целиком | Реализовано |
| A31 | File — capability, не modality | Реализовано |
| A32 | Token estimation — pluggable | Реализовано |
| A33 | Pricing — small optional value object | Реализовано |
| A34 | DDF exceptions только для DDF logic | Реализовано |
| A35 | Guardrails — composable pipeline | Roadmap |
| A36 | Observability — OpenTelemetry-first, privacy default | Roadmap |
| A37 | Smart splitters — content primitives | Roadmap |
| A38 | Нет generic Retriever/VectorStore | Принцип |
| A39 | Agent abstractions отложены | Принцип |
| A40 | AI API остаётся близким к OpenAI SDK | Реализовано частично |

### DDF-A20–A24. Граница и каталог AI

**Проблема.** AI не должен тянуть SDK в core или скрывать provider-specific возможности ещё одним универсальным DSL. Один catalog должен обслуживать разные приложения без навязанного registry/persistence/policy.

**Решение.** `ddf.ai` ставится extra; для OpenAI-compatible providers используется официальный `AsyncOpenAI`. `RoutedOpenAI` композирует клиентов, подставляет model/provider и возвращает native SDK response. `ModelSpec` описывает id, provider, model, modalities, limits, capabilities и optional pricing — без `ModelOrm`, repository или priority/task/quality tags.

**Применение.** Храните policy strategy рядом с продуктом и catalog в config/DB/external registry по своему решению. Если у продукта одна модель, используйте SDK напрямую.

\* Архитектурный замысел называет `ModelSpec` immutable. Текущая Pydantic-конфигурация не включает `frozen=True`, поэтому воспринимайте экземпляр как конфигурационные данные по соглашению, но не рассчитывайте на enforced immutability до изменения реализации.

### DDF-A25–A29. От технической пригодности к политике

**Проблема.** Самая дешёвая или «умная» модель может не поддерживать image/tools/required context, а quality/latency/priority зависят от use case.

**Решение.** `model_matches` сначала отсекает по modalities, capabilities, output limit и context. Затем ordered pipeline выбирает среди кандидатов: `model_priority`, `provider_priority`, `cheapest_model`, `smallest_context`, generic `by_score`, optional async `semantic`. Стратегия возвращает `None`, если не уверена.

**Применение.** Ставьте последнюю deterministic fallback strategy. Semantic scorer может использовать embeddings, classifier, small LLM или rules, но не обязан существовать для routing-а.

### DDF-A30–A34. Request semantics, token, цена и ошибки

**Проблема.** URL в тексте не доказывает media input; file — container; token count зависит от provider/model/multimodal content, а provider errors полезны сами по себе.

**Решение.** Analyzer понимает структурированные `instructions`, input parts, tools, reasoning, structured output и max tokens; URL не скачивает и MIME не угадывает. `input_file` добавляет `FILE_INPUT`, а не modality. Token estimator callback optional. `ModelPricing` хранит USD per million input/output/cached tokens. Текущая error hierarchy — `AIError → ModelRoutingError → NoSuitableModelError`; OpenAI SDK exceptions не оборачиваются.

**Применение.** Без estimator cost/context strategy должна уступить fallback. Pricing — routing/observability primitive, не billing system.

### DDF-A35–A40. Safety, observability, content и scope

**Проблема.** AI safety/telemetry нужны, но преждевременные guardrail, RAG и agent frameworks закрепляют application-specific сложность.

**Решение.** В roadmap: composable input/output/tool guardrails; OpenTelemetry spans для calls/routing/tools/cost с `capture_inputs=false`/`capture_outputs=false` default; multimodal `Document → Blocks → Chunks` splitters. Не вводятся generic Retriever/VectorStore, graph/node/agent executor/memory/multi-agent runtime. UX направлен к `ai.responses.create`; low-level `router.route` остаётся для tests/evals.

**Последствия.** Guardrails, OTel integration и splitters сейчас не являются API. Приложение выбирает vector DB, retrieval, OTLP backend и privacy policy самостоятельно. Добавлять agent primitives можно лишь после повторяемых tool-loop/routing/parallel/prompt-chain/evaluator patterns.
