FROM python:3.14-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY ddf ./ddf
COPY tests/__init__.py ./tests/__init__.py
COPY tests/helpers/__init__.py ./tests/helpers/__init__.py
COPY tests/helpers/dsl ./tests/helpers/dsl
COPY tests/e2e/__init__.py ./tests/e2e/__init__.py
COPY tests/e2e/dsl/__init__.py ./tests/e2e/dsl/__init__.py
COPY tests/e2e/dsl/app.py ./tests/e2e/dsl/app.py

RUN uv pip install --system --no-cache ".[sqlalchemy]"

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "tests.e2e.dsl.app:app", "--host", "0.0.0.0", "--port", "8000"]
