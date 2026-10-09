FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    NTP_PORT=123

RUN apt-get update \
    && apt-get install -y --no-install-recommends libcap2-bin \
    && setcap 'cap_net_bind_service=+ep' /usr/local/bin/python3.13 \
    && apt-get purge -y --auto-remove libcap2-bin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --chown=nobody:nogroup app.py .

EXPOSE 8080
EXPOSE 123/udp
USER nobody
CMD ["python", "app.py"]
