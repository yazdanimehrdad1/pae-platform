# Database Storage Analysis: Time-Series Data for Modbus Register Readings

> **Stale — read as a sizing estimate, not as a description of the schema.** The row shape
> below (`device_id` / `register_address` / `value` / `quality` / `register_name`) does not
> match any current table; readings live in `device_points_readings`, keyed by
> `device_point_id`. The TimescaleDB hypertables, compression and retention policies this
> document assumes are also not implemented — no migration calls `create_hypertable`.

## Overview

This document analyzes storage requirements and database design recommendations for storing time-series data from Modbus devices.

**Configuration:**
- 30 devices
- 100 registers per device
- Variable polling intervals (5s, 30s, 60s)

---

## Data Volume Calculations

### Scenario 1: 5-Second Polling

#### Row Count
- Total registers: 30 devices × 100 registers = **3,000 registers**
- Readings per minute: 3,000 × 12 = **36,000 rows/minute**
- Readings per hour: 36,000 × 60 = **2,160,000 rows/hour**
- Readings per day: 2,160,000 × 24 = **51,840,000 rows/day**
- Readings per month: 51,840,000 × 30 = **1,555,200,000 rows/month** (1.55 billion)

#### Storage Size Per Row
```
timestamp TIMESTAMPTZ      -- 8 bytes
device_id INTEGER          -- 4 bytes
register_address INTEGER   -- 4 bytes
value DOUBLE PRECISION    -- 8 bytes
quality TEXT              -- ~5 bytes avg ('good' = 4 chars)
register_name TEXT        -- ~20 bytes avg
data_type TEXT            -- ~6 bytes avg
unit TEXT                 -- ~3 bytes avg
PostgreSQL row overhead   -- ~24 bytes
Index overhead (partial)  -- ~10 bytes (amortized)
────────────────────────────────────────────
Total per row:            ~88 bytes average
```

#### Storage Requirements (5-Second Polling)

**Uncompressed:**
- Per day: 51,840,000 rows × 88 bytes = **4.26 GB/day**
- Per month: 1,555,200,000 rows × 88 bytes = **127.8 GB/month**
- Per year: ~**1.53 TB/year**

**With TimescaleDB Compression (3-5x typical):**
- Per day compressed: **~0.85-1.4 GB/day**
- Per month compressed: **~25.6-42.6 GB/month**
- Per year compressed: **~307-512 GB/year**

**With Indexes (add ~20-30% overhead):**
- Per month with indexes: **~30-50 GB/month**
- Per year with indexes: **~360-600 GB/year**

---

### Scenario 2: 30-Second Polling

#### Row Count
- Total registers: 30 devices × 100 registers = **3,000 registers**
- Readings per minute: 3,000 × 2 = **6,000 rows/minute**
- Readings per hour: 6,000 × 60 = **360,000 rows/hour**
- Readings per day: 360,000 × 24 = **8,640,000 rows/day**
- Readings per month: 8,640,000 × 30 = **259,200,000 rows/month** (259 million)

#### Storage Requirements (30-Second Polling)

**Uncompressed:**
- Per day: 8,640,000 rows × 88 bytes = **0.71 GB/day**
- Per month: 259,200,000 rows × 88 bytes = **21.3 GB/month**
- Per year: ~**255 GB/year**

**With TimescaleDB Compression (3-5x typical):**
- Per day compressed: **~0.14-0.24 GB/day**
- Per month compressed: **~4.3-7.1 GB/month**
- Per year compressed: **~51-85 GB/year**

**With Indexes (add ~20-30% overhead):**
- Per month with indexes: **~5.2-9.2 GB/month**
- Per year with indexes: **~62-110 GB/year**

---

### Scenario 3: 60-Second Polling

#### Row Count
- Total registers: 30 devices × 100 registers = **3,000 registers**
- Readings per minute: 3,000 × 1 = **3,000 rows/minute**
- Readings per hour: 3,000 × 60 = **180,000 rows/hour**
- Readings per day: 180,000 × 24 = **4,320,000 rows/day**
- Readings per month: 4,320,000 × 30 = **129,600,000 rows/month** (130 million)

#### Storage Requirements (60-Second Polling)

**Uncompressed:**
- Per day: 4,320,000 rows × 88 bytes = **0.36 GB/day**
- Per month: 129,600,000 rows × 88 bytes = **10.7 GB/month**
- Per year: ~**128 GB/year**

**With TimescaleDB Compression (3-5x typical):**
- Per day compressed: **~0.07-0.12 GB/day**
- Per month compressed: **~2.1-3.6 GB/month**
- Per year compressed: **~25-43 GB/year**

**With Indexes (add ~20-30% overhead):**
- Per month with indexes: **~2.6-4.7 GB/month**
- Per year with indexes: **~31-56 GB/year**

---

## Comparison Summary

| Polling Interval | Rows/Day | Rows/Month | Storage/Day (Compressed) | Storage/Month (Compressed) | Storage/Year (Compressed) |
|------------------|----------|------------|--------------------------|----------------------------|---------------------------|
| **5 seconds**    | 51.8M    | 1.55B      | 0.85-1.4 GB              | 25.6-42.6 GB               | 307-512 GB                |
| **30 seconds**   | 8.6M     | 259M       | 0.14-0.24 GB             | 4.3-7.1 GB                 | 51-85 GB                  |
| **60 seconds**   | 4.3M     | 130M       | 0.07-0.12 GB             | 2.1-3.6 GB                 | 25-43 GB                  |

### Storage Reduction Factors

- **30-second vs 5-second:** ~6x reduction in storage (1/6th the data)
- **60-second vs 5-second:** ~12x reduction in storage (1/12th the data)
- **60-second vs 30-second:** ~2x reduction in storage (1/2 the data)

---

## Database Design Recommendation

### Single Table vs Separate Tables

#### Recommendation: **Single Table** (for all polling intervals)

**Why Single Table:**

1. **Manageable Scale**
   - Even at 5-second polling (1.55B rows/month), TimescaleDB handles this efficiently
   - Compression reduces storage significantly (3-5x)
   - Chunking keeps queries fast regardless of total size

2. **Operational Simplicity**
   - One table to manage, monitor, and backup
   - Single schema to maintain
   - Easier migrations and updates

3. **Query Performance**
   - Proper indexing makes device_id filtering fast
   - Chunk exclusion limits scans to relevant time ranges
   - Continuous aggregates help with longer time ranges

4. **Cross-Device Capabilities**
   - Easy to compare devices
   - Aggregate across all devices
   - Simpler analytics

**When Separate Tables Make Sense:**
- Device-specific retention policies required
- Regulatory isolation requirements
- Rarely query across devices
- Maintenance windows are critical

---

## Storage Strategy

### Compression Policy
```sql
-- Compress data older than 7 days
SELECT add_compression_policy('register_readings', INTERVAL '7 days');
```
- Reduces storage by 3-5x
- Minimal query performance impact
- Automatic background compression

### Retention Policy
```sql
-- Drop data older than 1 year (adjust as needed)
SELECT add_retention_policy('register_readings', INTERVAL '1 year');
```
- Keeps storage bounded
- Automatic cleanup

### Continuous Aggregates
```sql
-- Pre-aggregate to reduce storage for historical data
CREATE MATERIALIZED VIEW register_readings_hourly
WITH (timescaledb.continuous) AS
SELECT 
  time_bucket('1 hour', timestamp) AS hour,
  device_id,
  register_address,
  AVG(value) as avg_value,
  MIN(value) as min_value,
  MAX(value) as max_value
FROM register_readings
GROUP BY hour, device_id, register_address;
```
- Store hourly aggregates for older data
- Keep raw data for recent period (e.g., last 7 days)
- Reduces long-term storage

---

## Recommended Schema

```sql
CREATE TABLE register_readings (
  -- Core identification
  timestamp TIMESTAMPTZ NOT NULL,
  device_id INTEGER NOT NULL,
  register_address INTEGER NOT NULL,
  
  -- Value
  value DOUBLE PRECISION NOT NULL,
  
  -- Quality/Status (important for historians)
  quality TEXT DEFAULT 'good',  -- 'good', 'bad', 'uncertain', 'substituted'
  
  -- Denormalized for performance (avoid joins)
  register_name TEXT,  -- From register_map, for faster queries
  data_type TEXT,      -- 'float', 'int16', 'uint16', 'bool'
  unit TEXT,           -- 'V', 'A', 'kW', '°C', etc.
  
  -- Primary key
  PRIMARY KEY (timestamp, device_id, register_address)
);

-- Convert to hypertable (chunks by day)
SELECT create_hypertable('register_readings', 'timestamp', 
  chunk_time_interval => INTERVAL '1 day');

-- Critical index for query performance
CREATE INDEX idx_device_register_time 
ON register_readings (device_id, register_address, timestamp DESC);
```

---

## Query Performance Expectations

### With Proper Indexing

**Latest Value Query:**
```sql
SELECT * FROM register_readings
WHERE device_id = 1 AND register_address = 100
ORDER BY timestamp DESC LIMIT 1;
```
- **Expected:** < 10ms (uses index, scans recent chunk)

**Time-Series Query (1 hour, 4 registers):**
```sql
SELECT timestamp, register_address, value
FROM register_readings
WHERE device_id = 1 
AND register_address IN (1, 2, 3, 4)
AND timestamp BETWEEN start_time AND end_time
ORDER BY timestamp, register_address;
```
- **5-second polling:** ~2,880 rows, < 50ms
- **30-second polling:** ~480 rows, < 20ms
- **60-second polling:** ~240 rows, < 15ms

**Time-Series Query (72 hours, 4 registers):**
```sql
-- Same query as above, 72-hour range
```
- **5-second polling:** ~207,360 rows, < 500ms (consider using continuous aggregates)
- **30-second polling:** ~34,560 rows, < 200ms
- **60-second polling:** ~17,280 rows, < 100ms

---

## Storage Estimates by Polling Interval

### 5-Second Polling
- **Monthly storage (compressed):** ~25.6-42.6 GB
- **Yearly storage (compressed):** ~307-512 GB
- **With indexes:** Add 20-30% overhead

### 30-Second Polling
- **Monthly storage (compressed):** ~4.3-7.1 GB
- **Yearly storage (compressed):** ~51-85 GB
- **With indexes:** Add 20-30% overhead

### 60-Second Polling
- **Monthly storage (compressed):** ~2.1-3.6 GB
- **Yearly storage (compressed):** ~25-43 GB
- **With indexes:** Add 20-30% overhead

---

## Conclusion

**Single table is recommended for all polling intervals** because:

1. **Storage is manageable** even at 5-second polling with compression
2. **Performance is excellent** with proper indexing and chunking
3. **Operational simplicity** outweighs complexity of 30 separate tables
4. **TimescaleDB is designed** for this scale and use case

**Storage reduction strategies:**
- Use compression for data older than 7 days
- Implement retention policies to drop old data
- Use continuous aggregates for longer time ranges
- Consider downsampling for historical data

**Polling interval impact:**
- 30-second polling reduces storage by ~6x vs 5-second
- 60-second polling reduces storage by ~12x vs 5-second
- Choose polling interval based on operational requirements vs storage constraints

