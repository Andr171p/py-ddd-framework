# Realtime Tickets — тестовое приложение на DDF

Минимальное FastAPI-приложение на публичных API DDF: WebSocket-подписки на
заявки и HTTP-обновление статуса с публикацией realtime-события.

Конфиг — `pydantic-settings` (`Settings` + `WsConfig` с префиксом `WS_`).

## Контракт

| Endpoint | Назначение |
|----------|------------|
| `GET /health` | liveness |
| `GET /ready` | readiness |
| `WS /ws?subject=<id>&org=<org>` | realtime-канал |
| `POST /tickets/{ticket_id}/status` | обновление → `ticket.updated` |
| `POST /realtime/publish` | прямая публикация в комнату |

## Локальный запуск

```sh
export REDIS_URL=redis://localhost:6379/0
export REALTIME_BACKEND=redis
uv run --group test --extra redis uvicorn tests.apps.realtime_tickets.app:app --port 8001
```
