"""Loki HTTP log handler — pushes structured JSON logs to Grafana Loki."""

import json
import logging
import time
from threading import Thread
from queue import Queue, Empty

import httpx


class LokiHandler(logging.Handler):
    """Async HTTP handler that sends log records to Grafana Loki.

    Uses a background thread + queue to avoid blocking the bot.
    Labels: level, logger, module, function.
    """

    def __init__(self, url: str, labels: dict | None = None, batch_size: int = 50):
        super().__init__()
        self.url = url.rstrip("/") + "/loki/api/v1/push"
        self.labels = labels or {"app": "invoice-bot"}
        self.batch_size = batch_size
        self._queue: Queue = Queue()
        self._thread: Thread | None = None
        self._running = False

    def _label_string(self, extra: dict | None = None) -> str:
        parts = [f'{k}="{v}"' for k, v in self.labels.items()]
        if extra:
            parts += [f'{k}="{v}"' for k, v in extra.items() if isinstance(v, str)]
        return "{" + ",".join(parts) + "}"

    def emit(self, record: logging.LogRecord) -> None:
        ts_ns = int(record.created * 1e9)

        labels_extra = {
            "level": record.levelname.lower(),
            "logger": record.name,
        }

        stream = {
            "stream": {**self.labels, **labels_extra},
            "values": [[str(ts_ns), self.format(record)]],
        }
        self._queue.put(stream)

    def _worker(self) -> None:
        """Background thread: drain queue and push batches to Loki."""
        batch: list = []
        last_flush = time.monotonic()

        while self._running:
            try:
                stream = self._queue.get(timeout=0.5)
                batch.append(stream)
            except Empty:
                pass

            if batch and (len(batch) >= self.batch_size or time.monotonic() - last_flush > 3):
                self._flush(batch)
                batch.clear()
                last_flush = time.monotonic()

        # Final flush
        if batch:
            self._flush(batch)

    def _flush(self, batch: list) -> None:
        """Merge batch into a single Loki push."""
        # Merge streams with same labels
        merged: dict[str, list] = {}
        for s in batch:
            key = json.dumps(s["stream"], sort_keys=True)
            if key not in merged:
                merged[key] = s
            else:
                merged[key]["values"].extend(s["values"])

        payload = {"streams": list(merged.values())}
        try:
            httpx.post(self.url, json=payload, timeout=5)
        except Exception:
            pass  # Don't crash the bot if Loki is down

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = Thread(target=self._worker, daemon=True, name="loki-handler")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def close(self) -> None:
        self.stop()
        super().close()
