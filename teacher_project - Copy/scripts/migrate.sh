#!/usr/bin/env bash
set -euo pipefail

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set" >&2
  exit 1
fi

cd "$(dirname "$0")/../apps/api"
alembic upgrade head
echo "Migrations complete!"
