"""Small standard-library HTTP API for the transport control center."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import unquote

from passenger_state import PassengerState


class _Handler(BaseHTTPRequestHandler):
    state: PassengerState | None = None

    def do_GET(self) -> None:  # noqa: N802
        state = self.state
        if state is None:
            self.send_error(503, "Passenger state unavailable")
            return
        path = unquote(self.path.split("?", 1)[0]).rstrip("/")
        snapshot = state.snapshot().as_dict()
        expected = f"/api/bus/{snapshot['bus_id']}/status"
        if path not in {expected, "/api/status"}:
            self.send_error(404, "Unknown API endpoint")
            return
        body = json.dumps(snapshot).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


class PassengerApiServer:
    def __init__(self, state: PassengerState, host: str = "127.0.0.1", port: int = 8765) -> None:
        _Handler.state = state
        self.server = ThreadingHTTPServer((host, port), _Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return int(self.server.server_port)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()