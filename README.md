# Flask App with Prometheus, Grafana & Loki

A Python Flask application with a full observability stack — metrics, dashboards, and logs.

## Stack

| Service | Purpose | Port |
|---|---|---|
| Flask | Web application | 5001 |
| Prometheus | Metrics collection | 9090 |
| Grafana | Dashboards & visualization | 3000 |
| Loki | Log aggregation | 3100 |
| Promtail | Log shipping to Loki | 9080 |

## Getting Started

### Prerequisites
- Python 3.x
- Docker & Docker Compose

### Run the Flask app

```bash
pip install flask prometheus-client
python main.py
```

### Run the observability stack

```bash
docker compose up
```

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /` | Hello World |
| `GET /metrics` | Prometheus metrics |

## Metrics

| Metric | Type | Description |
|---|---|---|
| `app_request_count_total` | Counter | Total requests by method, endpoint, status |
| `app_request_latency_seconds` | Histogram | Request latency by endpoint |

## Accessing the Stack

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin / admin)
- **Loki logs**: Grafana → Explore → Loki → `{job="flask-app"}`

## Grafana Setup

1. Add Prometheus data source: `http://prometheus:9090`
2. Add Loki data source: `http://loki:3100`
3. Import dashboard ID `3662` or create your own with PromQL queries:

```
# Requests per second
rate(app_request_count_total[1m])

# 95th percentile latency
histogram_quantile(0.95, rate(app_request_latency_seconds_bucket[1m]))
```