FROM python:3.14-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY ddf ./ddf
COPY tests/apps ./tests/apps
COPY tests/helpers ./tests/helpers
COPY tests/__init__.py ./tests/__init__.py

RUN uv pip install --system --no-cache ".[rabbit,redis]"

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "tests.apps.realtime_tickets.app:app", "--host", "0.0.0.0", "--port", "8000"]
