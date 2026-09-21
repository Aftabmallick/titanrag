# Runbook RB-02: Qdrant Out-of-Memory (OOM) Recovery & Quantization Tuning

## Symptoms
- Alert: `QdrantMemoryPressureHigh` (Container RSS > 85% limit)
- Qdrant process killed with exit code 137 (OOMKilled)
- Hybrid search requests fail with `503 Service Unavailable: Vector backend unreachable`

## Root Cause Diagnosis
1. Inspect Qdrant memory consumption:
   ```bash
   docker stats titan-qdrant
   ```
2. Verify collection quantization and on-disk payload status:
   ```bash
   curl -s "http://localhost:6333/collections/titan_chunks" | jq .result.config
   ```
   - Check if `quantization_config` is `null` (Float32 unquantized vectors consume 4x more RAM).
   - Check if `on_disk_payload` is `false`.

## Immediate Mitigation
1. Restart container with temporary expanded memory limit:
   ```bash
   docker compose up -d titan-qdrant
   ```
2. Enable INT8 Scalar Quantization immediately:
   ```bash
   curl -X PATCH "http://localhost:6333/collections/titan_chunks" \
     -H "Content-Type: application/json" \
     -d '{
       "quantization_config": {
         "scalar": {
           "type": "int8",
           "quantile": 0.99,
           "always_ram": true
         }
       }
     }'
   ```
3. Trigger dead point vacuuming and segment compaction:
   ```bash
   python3 -c "from titan_backend.retrieval.vector_maintenance import QdrantMaintenanceManager; QdrantMaintenanceManager.optimize_collection('titan_chunks')"
   ```

## Prevention
- Always enable Binary Quantization (BQ) for ColPali visual embeddings (`titan_colpali_visual`).
- Store vector payloads `on_disk: true` to avoid RAM pinning for chunk text and metadata.
