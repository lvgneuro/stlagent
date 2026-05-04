FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY bot/ ./bot/
COPY .env ./

RUN pip install uv && \
    uv sync --frozen && \
    mv .venv /venv

ENV PATH="/venv/bin:$PATH"

CMD ["python", "-m", "bot.main"]