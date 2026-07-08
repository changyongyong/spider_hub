FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY master/requirements.txt /app/master/requirements.txt
RUN pip install --no-cache-dir -r /app/master/requirements.txt

COPY master/ /app/master/

WORKDIR /app/master

EXPOSE 8000

CMD ["python", "-m", "src.server"]
