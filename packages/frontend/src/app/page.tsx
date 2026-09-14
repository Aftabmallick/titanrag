export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8 bg-slate-950">
      <div className="z-10 max-w-4xl w-full text-center space-y-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-sky-500/30 bg-sky-500/10 text-sky-400 text-xs font-semibold uppercase tracking-wider">
          Phase 1 Active • Core Infrastructure Online
        </div>
        <h1 className="text-5xl font-extrabold tracking-tight bg-gradient-to-r from-sky-400 via-indigo-300 to-white bg-clip-text text-transparent">
          TitanRAG Enterprise
        </h1>
        <p className="text-slate-400 max-w-xl mx-auto text-lg">
          Zero-leakage multi-tenant multimodal retrieval-augmented generation engine with Transactional Outbox, in-process ONNX routing, and defense-in-depth isolation.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-8 text-left">
          <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/50 backdrop-blur">
            <h3 className="text-sky-400 font-semibold mb-1">FastAPI REST & Outbox</h3>
            <p className="text-slate-400 text-sm">Transactional Outbox relay synchronizing PostgreSQL and Qdrant with zero-loss guarantees.</p>
          </div>
          <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/50 backdrop-blur">
            <h3 className="text-sky-400 font-semibold mb-1">Decoupled Workers</h3>
            <p className="text-slate-400 text-sm">Partitioned Celery priority queues with bounded child memory to prevent ML OOM crashes.</p>
          </div>
          <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/50 backdrop-blur">
            <h3 className="text-sky-400 font-semibold mb-1">Observability Stack</h3>
            <p className="text-slate-400 text-sm">Full OTLP tracing to Jaeger, Prometheus metrics, and provisioned Grafana dashboards.</p>
          </div>
        </div>
      </div>
    </main>
  );
}
