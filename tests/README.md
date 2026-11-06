Run all tests, including the rate limiter's production Lua scripts:

```sh
uv run --with "fakeredis[lua]" python -m unittest discover -s tests -v
```

The Lua tests use fakeredis and a Lua runtime, with controlled Redis time for
window boundaries and refill checks. No Redis server is required. Without
`fakeredis[lua]`, the integration tests are skipped; unit and FastAPI tests still run.
