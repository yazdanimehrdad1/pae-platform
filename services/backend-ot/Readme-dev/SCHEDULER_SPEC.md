# Scheduler Architecture Specification

## Summary

APScheduler with Redis leader election for Kubernetes multi-replica deployment. Key requirements:

• **Two-level locking**: Leader election lock (`scheduler:leader`, 30-60s TTL) + per-job execution lock (`scheduler:job:{job_id}:{timestamp}`, job duration + buffer)

• **Heartbeat mechanism**: Leader renews lock every 10-15 seconds (1/3 of TTL) via background task; if renewal fails, stop executing and attempt reacquisition

• **Pre-execution verification**: Before each job, verify (1) leader lock ownership matches pod ID, (2) acquire per-job lock atomically, (3) check Redis connectivity

• **Redis failure handling**: On connection loss, leader stops jobs immediately, attempts reconnection with exponential backoff (1s→60s max), resumes when reconnected and leadership reacquired

• **Lock ownership checks**: Always verify lock value matches pod identifier before execution/renewal; use atomic Redis `SET NX EX` operations

• **Failover behavior**: If leader dies, lock expires after TTL (30-60s), another pod acquires leadership; maximum failover time is lock TTL duration

• **Monitoring**: Log leader acquisitions/losses, job executions/skips, lock operations, and failover events at appropriate log levels (info/warning/error)

• **Configuration**: Leader lock TTL (30-60s), heartbeat interval (10-15s), per-job lock TTL (job duration + buffer), pod identifier from `HOSTNAME` or `POD_NAME`

• **Edge cases**: Prevent split-brain by verifying ownership; use Redis server-side TTL (not client-side); set per-job lock TTL to prevent mid-execution expiration

• **Graceful degradation**: API continues functioning if Redis unavailable; scheduler jobs pause until Redis restored; log all failures for monitoring

## Remaining Scheduler Tasks

**Last Updated:** December 19, 2024

**Enhancements:**
- Add error handling and retry logic — backoff, jitter for polling jobs
- Add scheduler status/monitoring endpoint (optional) — `GET /scheduler/status` for health checks

**Testing:**
- Test scheduler with single pod deployment
- Test scheduler with multiple pods — verify no duplicate execution
