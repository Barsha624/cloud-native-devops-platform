"""Task-management REST API.

Tasks live in process memory, so they are lost on restart and are not shared
between processes or Kubernetes replicas. See "Limitations" in the README.
"""

import hmac
import json
import logging
import os
import time
from itertools import count

from flask import Flask, g, jsonify, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from werkzeug.exceptions import HTTPException

MAX_TITLE_LENGTH = 200
PUBLIC_ENDPOINTS = {"health", "version", "metrics"}


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line, easy for log tools to parse."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())


def validate_title(value: object) -> str:
    """Return a cleaned title or raise ValueError with a message for the client."""
    if not isinstance(value, str):
        raise ValueError("title must be a string")
    title = value.strip()
    if not title:
        raise ValueError("title must not be empty")
    if len(title) > MAX_TITLE_LENGTH:
        raise ValueError(f"title must be at most {MAX_TITLE_LENGTH} characters")
    return title


def error_response(message: str, status: int):
    return jsonify(error=message), status


def create_app() -> Flask:
    app = Flask(__name__)
    configure_logging()

    api_key = os.environ.get("API_KEY", "")
    app_version = os.environ.get("APP_VERSION", "dev")

    tasks: dict[int, dict] = {}
    next_id = count(start=1)

    registry = CollectorRegistry()
    request_count = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
        registry=registry,
    )
    request_latency = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "endpoint"],
        registry=registry,
    )

    @app.before_request
    def start_timer_and_check_key():
        g.start_time = time.perf_counter()
        if api_key and request.endpoint not in PUBLIC_ENDPOINTS:
            supplied = request.headers.get("X-API-Key", "")
            if not hmac.compare_digest(supplied, api_key):
                return error_response("missing or invalid API key", 401)

    @app.after_request
    def record_metrics(response):
        # Use the route pattern, not the raw URL, so metric labels stay few.
        endpoint = request.url_rule.rule if request.url_rule else "unmatched"
        elapsed = time.perf_counter() - g.get("start_time", time.perf_counter())
        request_count.labels(request.method, endpoint, response.status_code).inc()
        request_latency.labels(request.method, endpoint).observe(elapsed)
        return response

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        return error_response(error.description or error.name, error.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        app.logger.exception("unhandled error")
        return error_response("internal server error", 500)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/version")
    def version():
        return jsonify(version=app_version)

    @app.get("/metrics")
    def metrics():
        return generate_latest(registry), 200, {"Content-Type": CONTENT_TYPE_LATEST}

    @app.get("/tasks")
    def list_tasks():
        return jsonify(list(tasks.values()))

    @app.post("/tasks")
    def create_task():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return error_response("request body must be a JSON object", 400)
        try:
            title = validate_title(payload.get("title"))
        except ValueError as exc:
            return error_response(str(exc), 400)

        task = {"id": next(next_id), "title": title, "done": False}
        tasks[task["id"]] = task
        app.logger.info("task created id=%s", task["id"])
        return jsonify(task), 201

    @app.get("/tasks/<int:task_id>")
    def get_task(task_id: int):
        task = tasks.get(task_id)
        if task is None:
            return error_response("task not found", 404)
        return jsonify(task)

    @app.patch("/tasks/<int:task_id>")
    def update_task(task_id: int):
        task = tasks.get(task_id)
        if task is None:
            return error_response("task not found", 404)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not payload:
            return error_response("request body must be a non-empty JSON object", 400)

        try:
            if "title" in payload:
                task["title"] = validate_title(payload["title"])
            if "done" in payload:
                if not isinstance(payload["done"], bool):
                    raise ValueError("done must be true or false")
                task["done"] = payload["done"]
        except ValueError as exc:
            return error_response(str(exc), 400)
        return jsonify(task)

    @app.delete("/tasks/<int:task_id>")
    def delete_task(task_id: int):
        if tasks.pop(task_id, None) is None:
            return error_response("task not found", 404)
        app.logger.info("task deleted id=%s", task_id)
        return "", 204

    return app


if __name__ == "__main__":
    # Development server only. Containers run gunicorn instead.
    create_app().run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
    )
