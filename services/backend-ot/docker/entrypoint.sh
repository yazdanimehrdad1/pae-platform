#!/bin/bash
set -e

echo "Starting application entrypoint..."

# Wait for PostgreSQL to be ready (with timeout)
echo "Waiting for PostgreSQL to be ready..."
timeout=60
while [ $timeout -gt 0 ]; do
    # Use Python to check database connection
    if python -c "
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path('/app/src')))
try:
    from db.connection import check_db_health
    result = asyncio.run(check_db_health())
    sys.exit(0 if result else 1)
except Exception as e:
    print(f'Health check error: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1; then
        echo "PostgreSQL is ready!"
        break
    else
        # Show error on first attempt or every 10 seconds
        if [ $timeout -eq 60 ] || [ $((timeout % 10)) -eq 0 ]; then
            echo "PostgreSQL health check failed, retrying..."
        fi
    fi
    echo "Waiting for PostgreSQL... ($timeout seconds remaining)"
    sleep 1
    timeout=$((timeout-1))
done

if [ $timeout -eq 0 ]; then
    echo "ERROR: PostgreSQL health check timeout"
    exit 1
fi

# Run database migrations unless disabled.
# Default is "true" so docker-compose / local dev behaviour is unchanged. In
# Kubernetes the app Deployment sets RUN_MIGRATIONS_ON_START=false and a dedicated
# migration Job (ArgoCD PreSync hook) owns the schema, so replicas don't race.
RUN_MIGRATIONS_ON_START="${RUN_MIGRATIONS_ON_START:-true}"

if [ "$RUN_MIGRATIONS_ON_START" = "true" ]; then
    echo "Running database migrations..."
    python scripts/migrate_db.py
    MIGRATION_EXIT_CODE=$?

    if [ $MIGRATION_EXIT_CODE -ne 0 ]; then
        echo "ERROR: Database migration failed with exit code $MIGRATION_EXIT_CODE"
        exit $MIGRATION_EXIT_CODE
    fi

    echo "Migrations completed successfully. Starting application..."
else
    echo "RUN_MIGRATIONS_ON_START=$RUN_MIGRATIONS_ON_START — skipping migrations. Starting application..."
fi

# Start the application (use exec to replace shell process)
exec "$@"

