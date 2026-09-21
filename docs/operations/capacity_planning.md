# TitanRAG Enterprise — Capacity Planning & Sizing Guide

## 1. Vector Memory Sizing Formulas

### Dense Embeddings (1536 Dimensions)
With INT8 Scalar Quantization in Qdrant:
$$\text{RAM per vector} = 1536 \times 1\text{ byte} = 1.5\text{ KB}$$
With HNSW index graph overhead ($\approx 1.3\times$ multiplier):
$$\text{Total RAM per 1M vectors} \approx 1,000,000 \times 1536 \times 1.3 \approx 2.0\text{ GB}$$

### Visual Multimodal Embeddings (ColPali Late Interaction)
With Binary Quantization (BQ) and 128-dim patch vectors:
$$\text{RAM per 1,000 Visual Pages} \approx 1,000 \times 1024\text{ patches} \times 16\text{ bytes} \approx 16\text{ MB}$$

---

## 2. Ingestion Worker Node Sizing

To process $N$ documents per day with average 10 pages per document ($10N$ pages/day):
- Docling OCR parsing speed: 1.5 seconds/page (CPU) or 0.2 seconds/page (GPU)
- Chunks per page: 4 chunks
- Contextual prepending + embedding batching: 0.1 seconds/chunk

$$\text{Daily compute hours} = \frac{10N \times 1.5}{3600} + \frac{40N \times 0.1}{3600}$$
For $N = 10,000$ docs/day:
$$\text{Daily compute} \approx 41.6\text{ CPU hours} + 11.1\text{ API hours} \approx 53\text{ hours}$$
**Recommendation**: 4 `celery-core` workers (2 vCPU each) + 2 `celery-heavy-ml` workers (4 vCPU each).

---

## 3. PostgreSQL & Connection Pool Sizing

$$\text{PgBouncer default\_pool\_size} = (2 \times \text{PostgreSQL CPU Cores}) + \text{Disk Spindle Count}$$
- 8 vCPU database node $\rightarrow$ `default_pool_size = 18` connections.
- Client connection capacity: up to 1,000 concurrent client streams.
