# Базовый образ с интерпретатором Python (см. пособие 4.8)
FROM python:3.12-slim

LABEL maintainer="devops@example.com"

# Не буферизовать вывод Python — логи сразу видны в docker logs
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Сначала ТОЛЬКО зависимости — слой закешируется
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Теперь код приложения
COPY app.py .

# Версия зашивается при сборке: --build-arg VERSION=$(git rev-parse --short HEAD)
ARG VERSION=dev
ENV APP_VERSION=$VERSION

# Не root
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

CMD ["python", "app.py"]
