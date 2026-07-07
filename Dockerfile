FROM node:22-bookworm AS webui-builder

WORKDIR /app/webui
COPY webui/package.json webui/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY webui/ ./
RUN pnpm build

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt \
    && python -m playwright install --with-deps chromium

COPY server/ /app/server/
COPY --from=webui-builder /app/webui/dist /app/webui/dist

WORKDIR /app/server

EXPOSE 8000

CMD ["python", "-m", "src.server", "--host", "0.0.0.0", "--port", "8000"]
