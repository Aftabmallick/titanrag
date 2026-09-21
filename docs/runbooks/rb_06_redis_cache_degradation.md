# Runbook RB-06: Redis Cache Degradation & Memory Eviction Management

## Symptoms
- Alert: `RedisMemoryUsageCritical` (> 90% maxmemory)
- Task dispatch fails with `OOM command not allowed when used memory > 'maxmemory'`
- Celery worker messages delayed or lost

## Diagnosis & Mitigation
1. Check Redis memory consumption and eviction stats:
   ```bash
   docker exec -it titan-redis redis-cli INFO memory
   ```
2. Identify memory hog keys:
   ```bash
   docker exec -it titan-redis redis-cli --bigkeys
   ```
3. If semantic query cache or presence tracking is bloating RAM, flush query cache keys safely without dropping Celery queues:
   ```bash
   docker exec -it titan-redis redis-cli EVAL "local keys = redis.call('keys', 'semantic_cache:*') for i=1,#keys,5000 do redis.call('del', unpack(keys, i, math.min(i+4999, #keys))) end return #keys" 0
   ```
4. Verify Celery task queues (`p0_interactive`, `p1_default`) remain intact.
