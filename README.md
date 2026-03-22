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

## Logs

Logs are written to `logs/app.log` and shipped to Loki via Promtail.

## Accessing the Stack

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin / admin)
- **Loki logs**: Grafana → Explore → Loki → `{job="flask-app"}`

## Grafana Setup

1. Add Prometheus data source: `http://prometheus:9090`
2. Add Loki data source: `http://loki:3100`
3. Import dashboard ID `3662` or create panels with PromQL:

```promql
# Requests per second
rate(app_request_count_total[1m])

# 95th percentile latency
histogram_quantile(0.95, rate(app_request_latency_seconds_bucket[1m]))

# Error rate
rate(app_request_count_total{status=~"5.."}[1m])
```

---

## Core Design Decisions

### Control Plane ↔ Agent Pattern

Since you're managing 5-20 servers, the system uses a hub-and-spoke model:

```
Control Plane (1x)          Agents (5-20x)
─────────────────           ──────────────
FastAPI API          ──►    Lightweight FastAPI
Celery Workers       ──►    Docker SDK locally
Redis + Postgres            Prometheus metrics
Grafana + Prometheus        cAdvisor sidecar
```

Each server runs a small agent (~200 lines) that:
- Accepts commands from control plane (pull image, manage volume)
- Exposes `/metrics` for Prometheus to scrape
- Validates requests using API key header

### API Key Auth Flow

```
Client                  FastAPI              PostgreSQL
  │                        │                     │
  │  X-API-Key: abc123     │                     │
  ├───────────────────────►│                     │
  │                        │  hash(abc123)?      │
  │                        ├────────────────────►│
  │                        │  ✓ valid + scopes   │
  │                        │◄────────────────────│
  │       200 OK           │                     │
  │◄───────────────────────│                     │
```

Keys are SHA-256 hashed in the DB — never stored in plaintext. Each key has scopes (`images:read`, `images:write`, `volumes:manage`, `admin`).

### Task Flow (e.g. Pull Image on 3 servers)

```
API Request
  │  POST /images/pull
  │  { image: "nginx:latest", servers: ["srv1","srv2","srv3"] }
  ▼
FastAPI
  │  dispatch 3 Celery tasks
  │  return { job_id: "abc" }
  ▼
Celery Workers (parallel)
  │  task 1: agent_service.pull(srv1, "nginx:latest")
  │  task 2: agent_service.pull(srv2, "nginx:latest")
  │  task 3: agent_service.pull(srv3, "nginx:latest")
  ▼
Each Agent
  │  docker pull nginx:latest
  │  report status back
  ▼
Job Status: GET /tasks/abc
  { total: 3, done: 2, failed: 0, pending: 1 }
```

### Database Schema

```
api_keys          servers              jobs
─────────         ────────             ────
id                id                   id
name              hostname             task_id (celery)
key_hash          ip_address           type
scopes[]          port                 status
created_at        api_key              server_id
last_used_at      last_seen_at         payload (JSON)
                  agent_version        result (JSON)
                                       created_at
images                                 finished_at
──────
id               volumes              networks
server_id        ────────             ────────
name             id                   id
tag              server_id            server_id
image_id         name                 name
size_mb          driver               driver
pulled_at        mountpoint           scope
                 created_at           created_at
```

---

## Grafana Dashboards Plan

### Dashboard 1 — Fleet Overview

| Panel | Type | Metric |
|---|---|---|
| Servers online | Stat | `up{job="dockerops-agent"}` |
| Total containers running | Stat | `sum(docker_containers_running)` |
| CPU heatmap (all servers) | Heatmap | `docker_container_cpu_percent` |
| Memory usage per server | Bar gauge | `docker_container_memory_mb` |

### Dashboard 2 — Task Queue

| Panel | Type | Metric |
|---|---|---|
| Tasks queued | Stat | `celery_queue_length` |
| Tasks failed (1h) | Stat | `celery_task_failed_total` |
| Avg task duration | Graph | `celery_task_duration_seconds` |
| Task success rate | Gauge | rate calculation |

### Dashboard 3 — Volumes & Networks

| Panel | Type | Metric |
|---|---|---|
| Total volume size | Stat | `docker_volume_size_bytes` |
| Dangling volumes | Alert panel | custom metric |
| Networks per server | Table | `docker_networks_total` |

### Dashboard 4 — Alerts History
- Container down events timeline
- Image pull failures log
- Queue backlog history

---

## Alerting Rules

```yaml
# container_alerts.yml
- alert: ContainerDown
  expr: absent(docker_containers_running{name=~".+"})
  for: 1m
  labels:
    severity: critical

- alert: HighCPU
  expr: docker_container_cpu_percent > 85
  for: 5m
  labels:
    severity: warning

- alert: HighMemory
  expr: docker_container_memory_mb > 900
  for: 5m
  labels:
    severity: warning

# queue_alerts.yml
- alert: QueueBackedUp
  expr: celery_queue_length > 100
  for: 2m
  labels:
    severity: warning

# image_alerts.yml
- alert: ImagePullFailed
  expr: increase(docker_image_pull_failures_total[10m]) > 2
  labels:
    severity: critical
```

---

## Build Phases

### Phase 1 — Control Plane Skeleton (Week 1)
- [ ] Docker Compose: Redis, Postgres, FastAPI, Celery
- [ ] API key model + SHA-256 hashing + auth middleware
- [ ] Server registration endpoints (`POST /servers`, `GET /servers`)
- [ ] DB migrations with Alembic

### Phase 2 — Agent (Week 2)
- [ ] Lightweight FastAPI agent with Docker SDK
- [ ] Image pull/push/list endpoints on agent
- [ ] Volume + network management endpoints
- [ ] Agent API key validation
- [ ] `docker-compose.agent.yml` for easy deployment

### Phase 3 — Task Queue (Week 3)
- [ ] Celery app + Redis broker
- [ ] Multi-server task fan-out (pull image on N servers)
- [ ] Job status tracking in Postgres
- [ ] Beat scheduler for periodic health pings
- [ ] `GET /tasks/{job_id}` polling endpoint

### Phase 4 — Telemetry (Week 4)
- [ ] cAdvisor on each agent server
- [ ] Custom Prometheus exporter (queue metrics, pull metrics)
- [ ] Node Exporter for host-level metrics
- [ ] Loki log shipping from agents + control plane

### Phase 5 — Grafana (Week 5)
- [ ] 4 dashboards auto-provisioned via JSON
- [ ] All 4 alert rules wired to Alertmanager
- [ ] Slack webhook for alert notifications
- [ ] Datasources auto-provisioned (Prometheus + Loki)

### Phase 6 — Hardening (Week 6)
- [ ] TLS between control plane and agents (mTLS optional)
- [ ] Rate limiting on API (slowapi)
- [ ] API key rotation endpoint
- [ ] Deployment docs + agent install script (`curl | bash`)
- [ ] Health + readiness probes for all services

---

## Tech Stack Summary

```
Layer             Technology
─────────────     ──────────────────────────────
API               FastAPI + Uvicorn
Auth              API Keys (SHA-256, scoped)
Task Queue        Celery + Redis
Scheduler         Celery Beat
Database          PostgreSQL + SQLAlchemy + Alembic
Docker SDK        docker-py
Metrics           Prometheus + cAdvisor + Node Exporter
Logs              Loki + Promtail
Dashboards        Grafana (auto-provisioned)
Alerting          Alertmanager → Slack/Email
Containerization  Docker + Docker Compose
```
