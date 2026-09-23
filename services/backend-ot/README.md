# Modbus TCP FastAPI Microservice

A FastAPI-based REST API service for communicating with Modbus TCP servers using pymodbus.

## Features

- **GET /api/healthz**: Health check endpoint with connection test and small read verification
- Robust error handling with proper HTTP status codes
- Environment variable configuration
- Clean connection management (no socket leaks)
- **Distributed Scheduler**: APScheduler with Redis-based leader election for multi-replica Kubernetes deployments

## Scheduler Implementation

The service includes a distributed scheduler system for periodic Modbus polling and data storage jobs. **Step 1**: Added the APScheduler dependency to pyproject.toml for async job scheduling. **Step 2**: Configured scheduler settings in config.py including leader lock TTL, heartbeat interval, and pod identification. **Step 3**: Implemented Redis-based distributed locking system with leader election and per-job execution locks in scheduler/locks.py. **Step 4**: Created scheduler engine in scheduler/engine.py that wraps all jobs with lock verification before execution. **Step 5**: Integrated scheduler lifecycle into FastAPI app startup/shutdown hooks for automatic initialization and cleanup.

## Installation

1. Install dependencies:
```bash
pip install -e .
```

## Configuration

The service uses environment variables for configuration. You can set them in two ways:

### Option 1: Using .env file (Recommended)

Create or edit `.env` file in the project root with your Modbus server settings:
```env
AGGREGATOR_MODBUS_HOST=192.168.1.100
AGGREGATOR_MODBUS_PORT=502
AGGREGATOR_SERVER_ID=1
MODBUS_TIMEOUT_S=5.0
MODBUS_RETRIES=3
```

The `.env` file is automatically loaded when the service starts.

### Option 2: Environment Variables

Set the following environment variables:

**Linux/Mac:**
```bash
export AGGREGATOR_MODBUS_HOST="192.168.1.100"      # Default: localhost
export AGGREGATOR_MODBUS_PORT="502"                 # Default: 502
export AGGREGATOR_SERVER_ID="1"              # Default: 1
export MODBUS_TIMEOUT_S="5.0"            # Default: 5.0
export MODBUS_RETRIES="3"                # Default: 3
```

**Windows PowerShell:**
```powershell
$env:AGGREGATOR_MODBUS_HOST="192.168.1.100"
$env:AGGREGATOR_MODBUS_PORT="502"
$env:AGGREGATOR_SERVER_ID="1"
$env:MODBUS_TIMEOUT_S="5.0"
$env:MODBUS_RETRIES="3"
```

## Running Locally

### Option 1: Using Makefile/Make Script (Recommended - Simplest)

**Windows (PowerShell):**
```powershell
# Configure your external Modbus server in .env file first
.\make.ps1 up-build

# View all available commands
.\make.ps1
```

**Linux/Mac:**
```bash
# Configure your external Modbus server in .env file first
make up-build

# View all available commands
make help
```

**Common commands:**
```bash
# Windows PowerShell
.\make.ps1 up-build   # Build and start containers
.\make.ps1 up         # Start containers
.\make.ps1 down       # Stop containers
.\make.ps1 logs       # View logs
.\make.ps1 restart    # Restart containers
.\make.ps1 health     # Check service health
.\make.ps1 ps         # View container status

# Linux/Mac
make up-build   # Build and start containers
make up         # Start containers
make down       # Stop containers
make logs       # View logs
make restart    # Restart containers
make health     # Check service health
make ps         # View container status
```

The API will be available at `http://localhost:8000`

### Option 2: Using Docker Compose Directly

**Configure your external Modbus server in `.env` file:**
```bash
AGGREGATOR_MODBUS_HOST=192.168.1.100  # Your external Modbus server IP
AGGREGATOR_MODBUS_PORT=502
AGGREGATOR_SERVER_ID=1
```

**Then start the service:**
```bash
docker-compose up --build
```

**Or set environment variables directly:**
```bash
AGGREGATOR_MODBUS_HOST=192.168.1.100 docker-compose up --build
```

### Option 3: Direct Python Execution

Start the service with uvicorn:

```bash
PYTHONPATH=src uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Or run directly:

```bash
cd src && python -m main
```

The API will be available at `http://localhost:8000`

API documentation (Swagger UI) available at: `http://localhost:8000/docs`

## Docker Details

### Architecture Decision

**Single Container Approach:** The FastAPI service and Modbus client are kept in the same container because:
- The Modbus client is a Python library/module, not a separate service
- They share the same Python process - no network boundary needed
- Simpler deployment, debugging, and resource management
- Standard microservice pattern

### Docker Commands

**Build the image:**
```bash
docker build -t pae-backend-ot -f docker/Dockerfile .
```

**Run the container:**
```bash
docker run -p 8000:8000 \
  -e AGGREGATOR_MODBUS_HOST=192.168.1.100 \
  -e AGGREGATOR_MODBUS_PORT=502 \
  pae-backend-ot
```

**Run with docker-compose (connects to external Modbus server):**
```bash
# Make sure AGGREGATOR_MODBUS_HOST is set in .env or as environment variable
docker-compose up --build
```

**Stop services:**
```bash
docker-compose down
```

**View logs:**
```bash
docker-compose logs -f pae-backend-ot
```

## Example curl Commands

### Health Check

```bash
curl -X GET "http://localhost:8000/api/healthz" | jq
```

Expected response:
```json
{
  "ok": true,
  "host": "192.168.1.100",
  "port": 502,
  "device_id": 1,
  "detail": "Connection and read test successful"
}
```

## Error Handling

The service translates Modbus errors into appropriate HTTP status codes:

- **400 Bad Request**: Invalid Modbus parameters or illegal function/data address
- **503 Service Unavailable**: Connection failures
- **504 Gateway Timeout**: Request timeouts
- **500 Internal Server Error**: Unexpected errors

Example error response:
```json
{
  "detail": "Illegal data address - The data address received is not valid"
}
```

## TODO

### Observability (not implemented)

The `src/telemetry/` package (tracing + metrics) and the `/api/metrics` router were
removed and still need to be re-implemented:

- [ ] **Tracing** — OpenTelemetry spans around Modbus polls, DB writes, and API requests,
      exported to an OTLP collector. Propagate trace context across the scheduler jobs.
- [ ] **Metrics** — Prometheus metrics + a `/api/metrics` scrape endpoint. At minimum:
      poll duration/success/failure counters per device, register read latency,
      device_points_readings write throughput, scheduler leader-election state.

### Other

- [ ] Persistent pooled client connections
- [ ] Batch polling multiple addresses
- [ ] Word/byte-order conversions for 32/64-bit values

## Testing with a Modbus Simulator

For local testing, you can use a Modbus simulator like:
- [ModbusPal](https://modbuspal.sourceforge.net/)
- [pymodbus simulator](https://pymodbus.readthedocs.io/en/latest/source/example/simulator.html)

Then point the service to `localhost:502` and test the endpoints.

