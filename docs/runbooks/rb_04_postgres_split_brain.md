# Runbook RB-04: PostgreSQL Split-Brain, Connection Pool & RLS Isolation Recovery

## Symptoms
- Alert: `PgBouncerConnectionPoolExhausted` (> 90% client connections in use)
- `AppException: Could not obtain database connection from pool`
- Database CPU at 100% due to slow sequential scans or unindexed joins

## Root Cause Diagnosis
1. Inspect PgBouncer pool status:
   ```bash
   psql -h localhost -p 6432 -U postgres -d pgbouncer -c "SHOW POOLS;"
   psql -h localhost -p 6432 -U postgres -d pgbouncer -c "SHOW CLIENTS;"
   ```
2. Identify slow unindexed queries:
   ```sql
   SELECT pid, now() - query_start AS duration, query 
   FROM pg_stat_activity 
   WHERE state != 'idle' 
   ORDER BY duration DESC LIMIT 10;
   ```
3. Terminate hanging client connections:
   ```sql
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE state != 'idle' AND now() - query_start > interval '60 seconds';
   ```

## Immediate Mitigation
1. Increase PgBouncer reserve pool temporarily:
   ```bash
   docker exec -it titan-pgbouncer sed -i 's/default_pool_size = 20/default_pool_size = 50/' /etc/pgbouncer/pgbouncer.ini
   docker exec -it titan-pgbouncer pkill -HUP pgbouncer
   ```
2. Check Row-Level Security policy execution time:
   Ensure `(tenant_id, workspace_id)` indexes exist on all queried tables.
