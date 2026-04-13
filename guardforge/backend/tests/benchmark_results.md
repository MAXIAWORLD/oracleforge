# GuardForge Performance Benchmark Report

**Target**: `http://127.0.0.1:8004`

## `/api/scan`

- Requests: 1000/1000 (0 errors)
- Total duration: 5.62s
- Throughput: 178.1 req/s
- Latency p50: **5.38 ms**
- Latency p95: **7.12 ms**
- Latency p99: 8.48 ms
- Latency min/mean/max: 4.14 / 5.61 / 28.29 ms

### By payload type
- `short_no_pii` (143 req): p50=4.98ms p95=6.19ms
- `short_1_pii` (286 req): p50=5.05ms p95=6.29ms
- `medium_few_pii` (286 req): p50=5.38ms p95=6.56ms
- `long_many_pii` (143 req): p50=5.62ms p95=6.83ms
- `very_long` (142 req): p50=6.65ms p95=8.52ms

## `/api/tokenize`

- Requests: 1000/1000 (0 errors)
- Total duration: 9.26s
- Throughput: 108.0 req/s
- Latency p50: **8.97 ms**
- Latency p95: **11.3 ms**
- Latency p99: 13.46 ms
- Latency min/mean/max: 7.2 / 9.26 / 41.85 ms

### By payload type
- `short_no_pii` (143 req): p50=8.66ms p95=10.5ms
- `short_1_pii` (286 req): p50=8.81ms p95=10.63ms
- `medium_few_pii` (286 req): p50=8.64ms p95=10.58ms
- `long_many_pii` (143 req): p50=8.99ms p95=10.91ms
- `very_long` (142 req): p50=10.46ms p95=13.33ms
