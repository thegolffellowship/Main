#!/bin/sh
# Start the Tracker. Litestream replication runs BESIDE the app, never in
# front of it: a missing binary, bad config or unreachable bucket can only
# stop replication, never the app (the digest then says so). Without the four
# LITESTREAM_* variables nothing here changes from the plain gunicorn start.
HERE=$(cd "$(dirname "$0")" && pwd)

start_replication() {
  if [ -z "$LITESTREAM_ACCESS_KEY_ID" ] || [ -z "$LITESTREAM_SECRET_ACCESS_KEY" ] \
     || [ -z "$LITESTREAM_R2_ENDPOINT" ] || [ -z "$LITESTREAM_R2_BUCKET" ]; then
    echo "replication: not configured (LITESTREAM_* variables not all set)"; return 0
  fi
  if [ -z "$DATABASE_PATH" ]; then
    echo "replication: DATABASE_PATH is not set; nothing to replicate"; return 0
  fi
  GG_ARCHIVE_PATH="$(dirname "$DATABASE_PATH")/transactions_gg_archive.db"
  export GG_ARCHIVE_PATH
  BIN=$(python3 "$HERE/install_litestream.py") || { echo "replication: no litestream binary"; return 0; }
  while true; do
    "$BIN" replicate -config "$HERE/../litestream.yml"
    echo "replication: litestream exited ($?); restarting in 30 s"
    sleep 30
  done
}

start_replication &
exec gunicorn asgi_app:application -k uvicorn.workers.UvicornWorker --bind "0.0.0.0:${PORT:-8000}" --workers 1 --timeout 120
