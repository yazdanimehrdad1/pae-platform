# Redis Access Guide

This guide covers different ways to access and interact with the Redis cache used by the PAE Backend OT.

## Table of Contents

- [Connection Information](#connection-information)
- [redis-cli (Command Line Interface)](#redis-cli-command-line-interface)
- [RedisInsight (GUI Tool)](#redisinsight-gui-tool)
- [API Endpoints](#api-endpoints)
- [Common Operations](#common-operations)
- [Key Naming Convention](#key-naming-convention)

## Connection Information

**Redis Connection Details:**
- **Host:** `localhost` (from host machine) or `redis` (from Docker network)
- **Port:** `6379`
- **Database:** `0` (default)
- **Password:** None (default)
- **Key Prefix:** `pae_backend_ot` (all keys are prefixed with this)

**Docker Container:**
- Container Name: `pae-backend-ot-redis`
- Image: `redis:7-alpine`

## redis-cli (Command Line Interface)

### Connecting to Redis

**Option 1: Via Docker container (recommended)**
```bash
docker exec -it pae-backend-ot-redis redis-cli
```

**Option 2: From host machine (if Redis client is installed)**
```bash
redis-cli -h localhost -p 6379
```

### Basic Commands

Once connected to `redis-cli`, you can use the following commands:

#### List Keys

```bash
# List all keys (be careful with large datasets - can block Redis)
KEYS *

# List keys matching a pattern (includes prefix)
KEYS pae_backend_ot:*

# List polling keys
KEYS pae_backend_ot:poll:*

# List latest polling data
KEYS pae_backend_ot:poll:*:latest

# Count total keys
DBSIZE
```

#### Get Key Values

```bash
# Get a specific key (returns JSON string)
GET pae_backend_ot:poll:main-sel-751:latest

# Get and pretty-print JSON (from host machine)
docker exec pae-backend-ot-redis redis-cli GET "pae_backend_ot:poll:main-sel-751:latest" | python -m json.tool
```

#### Key Information

```bash
# Check if a key exists
EXISTS pae_backend_ot:poll:main-sel-751:latest

# Get remaining TTL (time to live) in seconds
TTL pae_backend_ot:poll:main-sel-751:latest
# Returns: -1 if no TTL, -2 if key doesn't exist, or seconds remaining

# Get the data type of a key
TYPE pae_backend_ot:poll:main-sel-751:latest

# Get memory usage of a key (in bytes)
MEMORY USAGE pae_backend_ot:poll:main-sel-751:latest
```

#### Safe Key Scanning (Production Recommended)

```bash
# Scan keys (safer than KEYS, doesn't block Redis)
SCAN 0 MATCH pae_backend_ot:* COUNT 100

# Continue scanning (use the cursor returned from previous command)
SCAN <cursor> MATCH pae_backend_ot:* COUNT 100
```

#### Delete Keys

```bash
# Delete a specific key
DEL pae_backend_ot:poll:main-sel-751:latest

# Delete multiple keys
DEL pae_backend_ot:poll:main-sel-751:latest pae_backend_ot:poll:main-sel-751:2024-11-10T07:32:48.190790+00:00

# Delete all keys matching a pattern (use with caution!)
# Note: This requires a script or multiple DEL commands
```

#### Server Information

```bash
# Get Redis server info
INFO

# Get memory statistics
INFO memory

# Get database statistics
INFO keyspace

# Test connection
PING
# Should return: PONG
```

### Quick One-Liners

```bash
# View all cache keys
docker exec pae-backend-ot-redis redis-cli KEYS "pae_backend_ot:*"

# View a specific cached value (formatted JSON)
docker exec pae-backend-ot-redis redis-cli GET "pae_backend_ot:poll:main-sel-751:latest" | python -m json.tool

# Count polling keys
docker exec pae-backend-ot-redis redis-cli --raw KEYS "pae_backend_ot:poll:*" | wc -l

# Check Redis health
docker exec pae-backend-ot-redis redis-cli PING
```

## RedisInsight (GUI Tool)

RedisInsight is the official GUI tool from Redis Labs. It provides a visual interface for browsing and managing Redis data.

### Installation

1. **Download RedisInsight:**
   - Visit: https://redis.com/redis-enterprise/redis-insight/
   - Download for your operating system (Windows, macOS, Linux)
   - Free and open source

2. **Install and Launch:**
   - Follow the installation instructions for your OS
   - Launch RedisInsight

### Connecting to Redis

1. **Add Database Connection:**
   - Click "Add Redis Database" or the "+" button
   - Enter connection details:
     - **Host:** `localhost`
     - **Port:** `6379`
     - **Database Alias:** `PAE Backend OT` (optional, for your reference)
     - **Database Name/Index:** `0`
     - **Username:** (leave empty)
     - **Password:** (leave empty)
   - Click "Add Redis Database"

2. **Connect:**
   - Click on your database connection
   - You should see the Redis database interface


## API Endpoints

The PAE Backend OT provides REST API endpoints for cache operations. All endpoints are available at `http://localhost:8000`.

### Health Check

**GET** `/cache/health`

Check Redis connection status.

**Response:**
```json
{
  "redis_connected": true,
  "status": "healthy"
}
```

**Example:**
```bash
curl http://localhost:8000/api/cache/health
```

### List All Keys

**GET** `/cache/keys?pattern={pattern}`

List all cached keys, optionally filtered by pattern.

**Parameters:**
- `pattern` (optional): Pattern to match (e.g., `poll:*`). If not provided, returns all keys.

**Response:**
```json
{
  "keys": [
    "poll:main-sel-751:latest",
    "poll:main-sel-751:2024-11-10T07:32:48.190790+00:00"
  ],
  "count": 2,
  "pattern": "poll:*"
}
```

**Examples:**
```bash
# List all keys
curl http://localhost:8000/api/cache/keys

# List polling keys
curl http://localhost:8000/api/cache/keys?pattern=poll:*

# List latest keys only
curl http://localhost:8000/api/cache/keys?pattern=poll:*:latest
```

### Get Key Value

**GET** `/cache/get/{key}`

Get the value of a specific cache key.

**Parameters:**
- `key`: The cache key (without prefix)

**Response:**
```json
{
  "key": "poll:main-sel-751:latest",
  "value": {
    "ok": true,
    "timestamp": "2024-11-10T07:32:48.190790+00:00",
    "data": { ... }
  },
  "exists": true
}
```

**Example:**
```bash
curl http://localhost:8000/api/cache/get/poll:main-sel-751:latest
```

### Check Key Exists

**GET** `/cache/exists/{key}`

Check if a key exists in the cache.

**Parameters:**
- `key`: The cache key (without prefix)

**Response:**
```json
{
  "key": "poll:main-sel-751:latest",
  "exists": true
}
```

**Example:**
```bash
curl http://localhost:8000/api/cache/exists/poll:main-sel-751:latest
```

### Set Key Value

**POST** `/cache/set`

Set a value in the cache.

**Request Body:**
```json
{
  "key": "test:key",
  "value": { "test": "data" },
  "ttl": 3600
}
```

**Response:**
```json
{
  "success": true,
  "key": "test:key",
  "message": "Value cached"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/cache/set \
  -H "Content-Type: application/json" \
  -d '{"key": "test:key", "value": {"test": "data"}, "ttl": 3600}'
```

### Delete Key

**DELETE** `/cache/delete/{key}`

Delete a specific key from the cache.

**Parameters:**
- `key`: The cache key (without prefix)

**Response:**
```json
{
  "success": true,
  "key": "poll:main-sel-751:latest",
  "message": "Key deleted"
}
```

**Example:**
```bash
curl -X DELETE http://localhost:8000/api/cache/delete/poll:main-sel-751:latest
```

### Clear All Cache

**DELETE** `/cache/clear`

⚠️ **WARNING:** This deletes ALL cache keys and associated data. Use with caution!

**Response:**
```json
{
  "success": true,
  "deleted_count": 5,
  "message": "Deleted 5 cache keys"
}
```

**Example:**
```bash
curl -X DELETE http://localhost:8000/api/cache/clear
```

## Common Operations

### View Latest Polling Data

**Via API:**
```bash
curl http://localhost:8000/api/cache/get/poll:main-sel-751:latest | python -m json.tool
```

**Via redis-cli:**
```bash
docker exec pae-backend-ot-redis redis-cli GET "pae_backend_ot:poll:main-sel-751:latest" | python -m json.tool
```

### List All Timestamped Polling Data

**Via API:**
```bash
curl "http://localhost:8000/api/cache/keys?pattern=poll:main-sel-751:*" | python -m json.tool
```

**Via redis-cli:**
```bash
docker exec pae-backend-ot-redis redis-cli KEYS "pae_backend_ot:poll:main-sel-751:*"
```

### Check Cache Size

**Via redis-cli:**
```bash
docker exec pae-backend-ot-redis redis-cli DBSIZE
```

### Monitor Cache Operations in Real-Time

**Via redis-cli:**
```bash
docker exec -it pae-backend-ot-redis redis-cli MONITOR
```

This will show all Redis commands as they execute. Press `Ctrl+C` to stop.

## Key Naming Convention

All cache keys are prefixed with `pae_backend_ot:` (configurable via `CACHE_KEY_PREFIX` environment variable).

### Polling Keys

**Latest Value:**
- Format: `pae_backend_ot:poll:main-sel-751:latest`
- Contains: Most recent polling data
- TTL: Configurable (default: 1 hour)

**Timestamped Values:**
- Format: `pae_backend_ot:poll:main-sel-751:{ISO_TIMESTAMP}`
- Example: `pae_backend_ot:poll:main-sel-751:2024-11-10T07:32:48.190790+00:00`
- Contains: Historical polling data at specific timestamp
- TTL: Configurable (default: 1 hour)

### Key Structure in API

When using API endpoints, **do not include the prefix**. The API automatically adds `pae_backend_ot:` prefix.

**Correct:**
```bash
curl http://localhost:8000/api/cache/get/poll:main-sel-751:latest
```

**Incorrect:**
```bash
curl http://localhost:8000/api/cache/get/pae_backend_ot:poll:main-sel-751:latest
```

## Troubleshooting

### Cannot Connect to Redis

1. **Check if Redis container is running:**
   ```bash
   docker ps | grep redis
   ```

2. **Check Redis logs:**
   ```bash
   docker logs pae-backend-ot-redis
   ```

3. **Test connection:**
   ```bash
   docker exec pae-backend-ot-redis redis-cli PING
   ```

### Keys Not Showing Up

1. **Check key prefix:** All keys are prefixed with `pae_backend_ot:`
2. **Use SCAN instead of KEYS:** For large datasets, use `SCAN` command
3. **Check TTL:** Keys may have expired

### Memory Issues

1. **Check memory usage:**
   ```bash
   docker exec pae-backend-ot-redis redis-cli INFO memory
   ```

2. **Find large keys:**
   ```bash
   docker exec pae-backend-ot-redis redis-cli --bigkeys
   ```

3. **Clear old timestamped keys:**
   ```bash
   # List timestamped keys
   docker exec pae-backend-ot-redis redis-cli KEYS "pae_backend_ot:poll:*:*" | grep -v ":latest"
   ```

## Additional Resources

- **Redis Documentation:** https://redis.io/docs/
- **Redis Commands:** https://redis.io/commands/
- **RedisInsight Documentation:** https://redis.io/docs/ui/insight/

