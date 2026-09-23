# Database Access Guide

This guide covers different ways to access and interact with the PostgreSQL/TimescaleDB database used by the PAE Backend OT.

## Table of Contents

- [Connection Information](#connection-information)
- [Testing the Connection](#testing-the-connection)
- [DBeaver Connection](#dbeaver-connection)
- [psql Command Line](#psql-command-line)
- [API Endpoints](#api-endpoints)
- [Common Operations](#common-operations)

## Connection Information

**Database Connection Details:**
- **Host:** `localhost` (from host machine) or `postgres` (from Docker network)
- **Port:** `5435` (host); `5432` inside the Docker network
- **Database:** `pae_backend_ot` (configurable via `POSTGRES_DB` environment variable)
- **Username:** `pae_backend_ot_user` (configurable via `POSTGRES_USER` environment variable)
- **Password:** `pae_backend_ot_password` (configurable via `POSTGRES_PASSWORD` environment variable)
- **Database Type:** PostgreSQL 16 with TimescaleDB extension

**Docker Container:**
- Container Name: `pae-backend-ot-postgres`
- Image: `timescale/timescaledb:latest-pg16`

**Connection String (Python/asyncpg):**
```
postgresql://pae_backend_ot_user:pae_backend_ot_password@localhost:5435/pae_backend_ot
```

**JDBC URL (for DBeaver and other JDBC tools):**
```
jdbc:postgresql://localhost:5435/pae_backend_ot
```

## Testing the Connection

### Method 1: API Health Check Endpoint (Easiest)

After the application starts, test the database connection via HTTP:

```bash
curl http://localhost:8000/api/db_health
```

**Response:**
- `true` - Database is connected and healthy
- `false` - Database connection failed

### Method 2: Check Application Logs

The application automatically tests the database connection on startup. Check the logs:

```bash
# View logs with database-related messages
docker-compose logs pae-backend-ot | grep -i postgres

# Or on Windows PowerShell:
docker-compose logs pae-backend-ot | Select-String -Pattern "PostgreSQL|database"
```

**Expected log messages:**
```
Connecting to PostgreSQL at postgres:5432/pae_backend_ot
Successfully connected to PostgreSQL
PostgreSQL database initialized successfully
```

### Method 3: Test Script (After Rebuild)

A test script is available to verify the connection:

```bash
# Rebuild container first (to include scripts directory)
docker-compose up -d --build

# Run the test script
docker-compose exec pae-backend-ot python scripts/test_db_connection.py
```

**Expected output:**
```
Testing database connection...
✓ Connection pool created
✓ Database health check passed
✓ PostgreSQL version: PostgreSQL 16.x ...
✓ TimescaleDB extension found (version: x.x.x)
✓ All connection tests passed!
```

### Method 4: Direct Python Test in Container

Test the connection directly using Python:

```bash
docker-compose exec pae-backend-ot python -c "import sys; sys.path.insert(0, '/app/src'); from db.connection import check_db_health; import asyncio; print('✓ Connected!' if asyncio.run(check_db_health()) else '✗ Failed')"
```

### Method 5: Check Container Health

Verify the PostgreSQL container is running and healthy:

```bash
# Check container status
docker-compose ps postgres

# Check PostgreSQL container logs
docker-compose logs postgres

# Test connection from container
docker-compose exec postgres pg_isready -U pae_backend_ot_user -d pae_backend_ot
```

## DBeaver Connection

DBeaver is a popular database management tool with a GUI interface.

### Connection Steps

1. **Open DBeaver**
   - Launch DBeaver application

2. **Create New Connection**
   - Click "New Database Connection" (plug icon) or `File > New > Database Connection`
   - Select **PostgreSQL** from the list

3. **Enter Connection Details**
   - **Host:** `localhost`
   - **Port:** `5435`
   - **Database:** `pae_backend_ot`
   - **Username:** `pae_backend_ot_user`
   - **Password:** `pae_backend_ot_password`
   - **JDBC URL:** `jdbc:postgresql://localhost:5435/pae_backend_ot` (auto-generated)

4. **Test Connection**
   - Click "Test Connection" button
   - DBeaver may prompt to download PostgreSQL driver (click "Download")
   - Should see "Connected" message

5. **Save and Connect**
   - Click "Finish" to save the connection
   - Double-click the connection to connect

### Connection Parameters Summary

| Parameter | Value |
|-----------|-------|
| Host | `localhost` |
| Port | `5435` (host) |
| Database | `pae_backend_ot` |
| Username | `pae_backend_ot_user` |
| Password | `pae_backend_ot_password` |
| JDBC URL | `jdbc:postgresql://localhost:5435/pae_backend_ot` |

**Note:** If you have custom values in your `.env` file, use those instead of the defaults.

## psql Command Line

`psql` is the PostgreSQL interactive terminal.

### Connecting via Docker

**Option 1: Execute psql in the container**
```bash
docker-compose exec postgres psql -U pae_backend_ot_user -d pae_backend_ot
```

**Option 2: Connect from host (if psql is installed)**
```bash
psql -h localhost -p 5435 -U pae_backend_ot_user -d pae_backend_ot
```

### Basic psql Commands

Once connected to `psql`, you can use the following commands:

```sql
-- List all databases
\l

-- List all tables in current database
\dt

-- List all schemas
\dn

-- Describe a table structure
\d table_name

-- List all extensions
\dx

-- Check TimescaleDB extension
SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';

-- Get PostgreSQL version
SELECT version();

-- Exit psql
\q
```

### Quick One-Liners

```bash
# Connect and run a query
docker-compose exec postgres psql -U pae_backend_ot_user -d pae_backend_ot -c "SELECT version();"

# Check if TimescaleDB is installed
docker-compose exec postgres psql -U pae_backend_ot_user -d pae_backend_ot -c "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';"

# List all tables
docker-compose exec postgres psql -U pae_backend_ot_user -d pae_backend_ot -c "\dt"

# List all databases
docker-compose exec postgres psql -U pae_backend_ot_user -d pae_backend_ot -c "\l"
```

## Database Migrations

### Running Migrations

The database migration system automatically tracks and runs pending migrations in order.

**Run all pending migrations:**
```bash
docker-compose exec pae-backend-ot python scripts/migrate_db.py
```

**What it does:**
- Finds all `.sql` files in `src/db/migrations/` directory
- Runs them in order (sorted by filename: 001, 002, 003, etc.)
- Tracks applied migrations in `schema_migrations` table
- Skips already applied migrations
- Runs each migration in a transaction (rolls back on failure)

**Expected output:**
```
Starting database migrations...
Found 4 migration file(s)
Found 0 already applied migration(s)
Running migration: 001_create_sites_table.sql
✓ Migration 001_create_sites_table completed
...
Running migration: 004_create_device_points_readings_table.sql
✓ Migration 004_create_device_points_readings_table completed
✓ Applied 4 new migration(s)
```

## API Endpoints

The PAE Backend OT provides REST API endpoints for database operations. All endpoints are available at `http://localhost:8000`.

### Database Health Check

**GET** `/api/db_health`

Check database connection status.

**Response:**
```json
true
```
or
```json
false
```

**Example:**
```bash
curl http://localhost:8000/api/db_health
```

## Common Operations

### View Database Version

**Via psql:**
```bash
docker-compose exec postgres psql -U pae_backend_ot_user -d pae_backend_ot -c "SELECT version();"
```

### Check TimescaleDB Extension

**Via psql:**
```bash
docker-compose exec postgres psql -U pae_backend_ot_user -d pae_backend_ot -c "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';"
```

### List All Tables

**Via psql:**
```bash
docker-compose exec postgres psql -U pae_backend_ot_user -d pae_backend_ot -c "\dt"
```

### View Database Size

**Via psql:**
```bash
docker-compose exec postgres psql -U pae_backend_ot_user -d pae_backend_ot -c "SELECT pg_size_pretty(pg_database_size('pae_backend_ot'));"
```

### Monitor Database Connections

**Via psql:**
```bash
docker-compose exec postgres psql -U pae_backend_ot_user -d pae_backend_ot -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'pae_backend_ot';"
```

## Troubleshooting

### Cannot Connect to Database

1. **Check if PostgreSQL container is running:**
   ```bash
   docker-compose ps postgres
   ```

2. **Check PostgreSQL logs:**
   ```bash
   docker-compose logs postgres
   ```

3. **Test connection from container:**
   ```bash
   docker-compose exec postgres pg_isready -U pae_backend_ot_user -d pae_backend_ot
   ```

4. **Verify environment variables:**
   ```bash
   docker-compose exec pae-backend-ot env | grep POSTGRES
   ```

### Connection Refused

- **Check port mapping:** Ensure port `5435` is not already in use
- **Check firewall:** Ensure port `5435` is not blocked
- **Verify container network:** Containers should be on the same Docker network

### Authentication Failed

- **Check credentials:** Verify `POSTGRES_USER` and `POSTGRES_PASSWORD` match
- **Check .env file:** Ensure environment variables are set correctly
- **Reset password:** You may need to recreate the container if credentials changed

### TimescaleDB Extension Not Found

TimescaleDB should be pre-installed in the `timescale/timescaledb` image. If you need to enable it:

```sql
-- Connect to database
docker-compose exec postgres psql -U pae_backend_ot_user -d pae_backend_ot

-- Create extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Verify
SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';
```

### Database Not Found

If the database doesn't exist, it should be created automatically by the container. Check:

```bash
# List all databases
docker-compose exec postgres psql -U pae_backend_ot_user -d postgres -c "\l"
```

If `pae_backend_ot` is missing, check the `POSTGRES_DB` environment variable in `docker-compose.yaml`.

## Migration Best Practices (TODO)

When creating and running database migrations, follow these best practices:

- **Make migrations additive when possible** — Add new tables/columns rather than removing existing ones
- **Test migrations on a copy of production data first** — Always test migrations with realistic data before applying to production
- **Backup before major migrations** — Create database backups before running migrations that modify existing tables or data
- **Use transactions** — Migrations should run in transactions so if a migration fails, it should roll back automatically

## Additional Resources

- **PostgreSQL Documentation:** https://www.postgresql.org/docs/
- **TimescaleDB Documentation:** https://docs.timescale.com/
- **asyncpg Documentation:** https://magicstack.github.io/asyncpg/
- **DBeaver Documentation:** https://dbeaver.com/docs/

