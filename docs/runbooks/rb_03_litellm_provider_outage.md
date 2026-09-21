# Runbook RB-03: LiteLLM Provider Outage & Failover Protocol

## Symptoms
- Alert: `LLMProviderErrorsHigh` (> 10 errors/min from upstream LLM provider)
- Users see `502 Bad Gateway` or `429 Rate Limit Exceeded` in chat streaming
- LiteLLM logs show `openai.RateLimitError` or `anthropic.InternalServerError`

## Root Cause Diagnosis
1. Inspect LiteLLM Proxy logs:
   ```bash
   docker logs --tail 100 titan-litellm
   ```
2. Check provider latency and failure metrics at `http://localhost:4000/metrics`.
3. Check circuit breaker trips in Redis:
   ```bash
   docker exec -it titan-redis redis-cli KEYS "circuit_breaker:*"
   ```

## Immediate Mitigation
1. Update LiteLLM routing rules to failover to backup provider:
   - Primary: `deepseek-ai/deepseek-v4-flash-0731`
   - Secondary: `azure/gpt-4o-mini`
   - Tertiary: `anthropic/claude-3-5-haiku-20241022`
2. If Zero Data Retention (ZDR) mode is active, ensure fallback endpoint is in the ZDR certified registry.
3. Reset tripped circuit breakers once upstream recovers:
   ```bash
   docker exec -it titan-redis redis-cli DEL "circuit_breaker:provider_litellm"
   ```

## Prevention
- Configure multi-provider fallbacks in `packages/infra/litellm/config.yaml`.
- Enforce token-bucket sliding rate limits per workspace.
