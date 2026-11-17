FROM python:3.12-slim

ARG VERSION=dev
LABEL org.opencontainers.image.title="ServerManager" \
      org.opencontainers.image.vendor="AtronixX-Core" \
      org.opencontainers.image.authors="AtronixX-Core (https://t.me/AtronixX_Core)" \
      org.opencontainers.image.description="Manage your servers over SSH from Telegram" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}"

RUN groupadd -r servermanager && useradd -r -g servermanager -d /app -s /usr/sbin/nologin servermanager \
    && apt-get update && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /data && chown -R servermanager:servermanager /app /data

USER servermanager
ENV PYTHONUNBUFFERED=1 DATA_DIR=/data
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python3 -c "import time,sys; d=open('/tmp/servermanager.hb').read(); sys.exit(0 if time.time()-float(d)<90 else 1)" || exit 1

ENTRYPOINT ["tini", "--"]
CMD ["python3", "main.py"]
