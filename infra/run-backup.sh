#!/bin/sh
set -eu
case "${1:-}" in ''|*[!0-9]*) echo 'Invalid plan id' >&2; exit 2;; esac
set -a
. /run/backup.env
set +a
# Same lock as the panel. timeout terminates the whole command group.
exec timeout --kill-after=10s 3600 flock -n -E 75 "/locks/plan-$1" sh -c '
  date -Iseconds
  borgmatic -c "/configs/plan-$1.yaml" create prune compact
  result=$?
  date -Iseconds
  echo "EXIT_CODE=$result"
  exit "$result"
' sh "$1"
