#!/usr/bin/env bash
# Start script for hosts like Render: prepare the database, then serve.
set -euo pipefail

python manage.py migrate --noinput
python manage.py ensure_admin

# Example shoes for a preview site. Turn off (SEED_DEMO=false) before real stock goes in.
if [ "${SEED_DEMO:-false}" = "true" ]; then
  python manage.py seed_demo
fi

exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}"
