from flask import Flask, Response, g, request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import logging
import os
import time

os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Define metrics
REQUEST_COUNT = Counter(
    'app_request_count_total',
    'Total request count',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'app_request_latency_seconds',
    'Request latency in seconds',
    ['endpoint']
)

@app.before_request
def start_timer():
    g.start = time.time()

@app.after_request
def record_metrics(response: Response) -> Response:
    if hasattr(g, 'start'):
        latency = time.time() - g.start
        REQUEST_LATENCY.labels(endpoint=request.path).observe(latency)
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.path,
        status=response.status_code
    ).inc()
    logger.info('%s %s %s', request.method, request.path, response.status_code)
    return response

# Expose /metrics endpoint for Prometheus to scrape
@app.route('/metrics')
def metrics():
    logger.info('Metrics endpoint accessed')
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.route('/')
def index():
    logger.info('Index endpoint accessed')
    return 'Hello World!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
