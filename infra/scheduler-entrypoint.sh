#!/bin/sh
set -eu
umask 077
. /usr/local/bin/load-secrets
# Cron does not inherit the container environment. Write a root-only shell env file;
# shlex.quote preserves secrets containing spaces or shell metacharacters.
python - <<'PY'
import os, shlex
from pathlib import Path
names = ['SOURCE_DB_PASSWORD', 'RESTORE_DB_PASSWORD', 'BORG_PASSPHRASE',
         'BORG_CONFIG_DIR', 'BORG_CACHE_DIR', 'BORG_SECURITY_DIR', 'TZ']
Path('/run/backup.env').write_text('\n'.join(f'{key}={shlex.quote(os.environ[key])}' for key in names) + '\n')
PY
exec "$@"
