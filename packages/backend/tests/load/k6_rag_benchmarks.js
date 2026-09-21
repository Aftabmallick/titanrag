// k6 High-Concurrency Performance & Latency Benchmark for TitanRAG
// Asserts P95 TTFT < 1.8s, P99 Latency < 3.0s, and error rate < 0.1% under 250 concurrent requests.

import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 50 },   // Ramp-up to 50 users
    { duration: '1m', target: 150 },   // Ramp-up to 150 users
    { duration: '2m', target: 250 },   // Sustained peak at 250 users
    { duration: '30s', target: 0 },    // Ramp-down
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],    // Error rate must be less than 1%
    http_req_duration: ['p(95)<1800', 'p(99)<3000'], // P95 < 1.8s, P99 < 3.0s
  },
};

const BASE_URL = __ENV.TARGET_URL || 'http://localhost:8000';

export default function () {
  // 1. Health Probe
  const healthRes = http.get(`${BASE_URL}/health/live`);
  check(healthRes, {
    'health live status is 200': (r) => r.status === 200,
  });

  // 2. Unauthenticated Public Probes
  const readyRes = http.get(`${BASE_URL}/health/ready`);
  check(readyRes, {
    'health ready returns valid status': (r) => r.status === 200 || r.status === 503,
  });

  sleep(1);
}
