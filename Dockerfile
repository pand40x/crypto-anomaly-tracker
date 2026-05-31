FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY anomaly_tracker ./anomaly_tracker

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
  && mkdir -p /app/outputs/live \
  && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

CMD ["python", "-m", "anomaly_tracker.cli", "serve"]
