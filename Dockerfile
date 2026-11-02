FROM python:3.12-slim-bookworm AS engine
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Europe/Moscow \
    BORG_CONFIG_DIR=/borg-home/config BORG_CACHE_DIR=/borg-home/cache \
    BORG_SECURITY_DIR=/borg-home/security
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client cron util-linux tzdata ca-certificates \
    build-essential pkg-config libssl-dev libacl1-dev liblz4-dev libzstd-dev libxxhash-dev \
    && rm -rf /var/lib/apt/lists/*
RUN ln -snf /usr/share/zoneinfo/Europe/Moscow /etc/localtime && echo Europe/Moscow > /etc/timezone
RUN pip install --no-cache-dir borgbackup==1.4.5 borgmatic==1.9.14
COPY infra/run-backup.sh /usr/local/bin/run-backup
COPY infra/scheduler-entrypoint.sh /usr/local/bin/scheduler-entrypoint
COPY infra/load-secrets.sh /usr/local/bin/load-secrets
RUN chmod 755 /usr/local/bin/run-backup /usr/local/bin/scheduler-entrypoint /usr/local/bin/load-secrets
ENTRYPOINT ["/usr/local/bin/scheduler-entrypoint"]
CMD ["cron", "-f"]

FROM engine AS panel
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod 755 /app/infra/panel-entrypoint.sh
ENV STATE_DIR=/state BACKUP_CONFIG_DIR=/configs BACKUP_CRON_DIR=/cron \
    BACKUP_LOG_DIR=/logs BACKUP_REPOSITORY_DIR=/repository BACKUP_LOCK_DIR=/locks
ENTRYPOINT ["/app/infra/panel-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2", "--timeout", "210", "--access-logfile", "-"]
