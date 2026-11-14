# Load: Realtime / WebSocket (Locust)

Стенд — тот же compose, что и E2E (`tests/e2e/docker/` через include).

```sh
make test-load          # UI http://127.0.0.1:8089 (+ открывает браузер)
make test-load-headless # baseline 100 users / 5m
```

UI: **http://127.0.0.1:8089/** (не через proxy).

`make test-load` ждёт, пока Locust начнёт слушать порт, и только потом
открывает браузер. Если открыть URL раньше времени, Яндекс/браузер покажет
`connectionfailure` — обнови страницу после строки
`Starting web interface at ...`.

Host нагрузки: `http://127.0.0.1:18001` (ws-a).

DSL — отдельный locustfile и стенд `tests/e2e/dsl/docker/`:

```sh
make test-load-dsl
```
