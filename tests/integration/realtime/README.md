# Integration: Realtime / WebSocket

Протокол, admission, лимитеры и broker-доставка в одном процессе
`realtime_tickets`. Redis/RabbitMQ — через testcontainers.

```sh
make test-integration-realtime
# или
uv run --group test --extra redis --extra rabbit pytest tests/integration/realtime -v
```

Конфиг — env (`pydantic-settings`); uvicorn поднимается через
`tests.helpers.tickets_server` (отдельный процесс на тест с уникальным
`subject`/`room` — изоляция важнее шаринга при shutdown/lease-сценариях).
