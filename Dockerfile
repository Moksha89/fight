FROM python:3.13-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apk add --no-cache postgresql-client \
    && addgroup -S roosterrun \
    && adduser -S -G roosterrun -u 10001 roosterrun
WORKDIR /app

COPY --chown=roosterrun:roosterrun server/ /app/server/
COPY --chown=roosterrun:roosterrun web/ /app/web/
COPY --chown=roosterrun:roosterrun scripts/ /app/scripts/
COPY --chown=roosterrun:roosterrun requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN mkdir -p /data && chown roosterrun:roosterrun /data

USER roosterrun
EXPOSE 8765
VOLUME ["/data"]

HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health/ready/', timeout=3)" || exit 1

CMD ["python", "server/manual_payments_server.py", "--host", "0.0.0.0", "--port", "8765", "--data-dir", "/data"]
