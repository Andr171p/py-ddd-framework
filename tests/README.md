Run all tests, including the rate limiter's production Lua scripts:

```sh
uv run --group test --extra sqlalchemy pytest tests -v
```

The Lua tests use fakeredis and a Lua runtime, with controlled Redis time for
window boundaries and refill checks. No Redis server is required. The `sqlalchemy`
extra enables the DSL integration tests. Without the `test` group, Lua tests are
skipped; without the `sqlalchemy` extra, DSL integration tests are skipped.
