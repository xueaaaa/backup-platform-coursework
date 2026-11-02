#!/bin/sh
set -eu
umask 077
. /usr/local/bin/load-secrets
python manage.py migrate --noinput
python manage.py collectstatic --noinput
chmod 755 /state
chmod -R a+rX /state/static
python manage.py bootstrap
exec "$@"
