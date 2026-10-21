#!/bin/bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

DIR=backups
mkdir -p "$DIR"
DEST="$DIR/materiales_$(date +%F_%H%M).sql.gz"
TMP="$DEST.tmp"
LOG="$DIR/backup.log"
trap 'rm -f "$TMP"' EXIT

{
  echo "[$(date '+%F %T')] inicio"
  docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" --clean --if-exists "$POSTGRES_DB"' | gzip > "$TMP"
  gzip -t "$TMP"
  if [ "$(stat -c %s "$TMP")" -lt 1000 ]; then
    echo "ERROR: backup demasiado pequeno, descartado"
    exit 1
  fi
  mv "$TMP" "$DEST"
  find "$DIR" -name 'materiales_*.sql.gz' -mtime +14 -delete
  echo "OK $DEST"
} >> "$LOG" 2>&1
