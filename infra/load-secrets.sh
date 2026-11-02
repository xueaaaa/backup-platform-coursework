#!/bin/sh
# Compose keeps using environment variables; Swarm mounts the same values as secrets.
load_backup_secret() {
    if [ -f "/run/secrets/$1" ]; then
        value=$(cat "/run/secrets/$1")
        export "$1=$value"
        unset value
    fi
}
for name in DJANGO_SECRET_KEY ADMIN_PASSWORD SOURCE_DB_PASSWORD RESTORE_DB_PASSWORD BORG_PASSPHRASE; do
    load_backup_secret "$name"
done
unset name
