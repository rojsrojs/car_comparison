"""Local web app for comparing the monthly cost of cars.

Usage: python app.py [--no-browser]     (or double-click start.bat)

Serves web/ and reads/writes data/cars.json. Listens on localhost only.
"""

import hashlib
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import build_v40

ROOT: Path = Path(__file__).parent
WEB_DIR: Path = (ROOT / "web").resolve()
CARS_PATH: Path = build_v40.CARS_PATH
HOST: str = "127.0.0.1"
PORT: int = 8765
URL: str = f"http://localhost:{PORT}/"

CONTENT_TYPES: dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}
ALLOWED_HOSTS: frozenset[str] = frozenset({f"localhost:{PORT}", f"127.0.0.1:{PORT}"})

_file_lock = threading.Lock()


def etag(raw: bytes) -> str:
    return '"' + hashlib.sha256(raw).hexdigest()[:16] + '"'


def is_valid(data: Any) -> bool:
    return (isinstance(data, dict) and isinstance(data.get("settings"), dict)
            and isinstance(data.get("cars"), list)
            and all(isinstance(c, dict) and isinstance(c.get("items"), list) for c in data["cars"]))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if not self._host_ok():
            return
        path = self.path.split("?", 1)[0]
        if path == "/api/data":
            with _file_lock:
                raw = CARS_PATH.read_bytes()
            self._send(200, raw, "application/json; charset=utf-8", etag(raw))
            return
        target = (WEB_DIR / (path.lstrip("/") or "index.html")).resolve()
        if WEB_DIR not in target.parents or not target.is_file() or target.suffix not in CONTENT_TYPES:
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        self._send(200, target.read_bytes(), CONTENT_TYPES[target.suffix])

    def do_PUT(self) -> None:
        if not self._host_ok():
            return
        if self.path != "/api/data":
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except (ValueError, json.JSONDecodeError):
            data = None
        if not is_valid(data):
            self._send(400, b"Invalid data", "text/plain; charset=utf-8")
            return
        with _file_lock:
            current = CARS_PATH.read_bytes()
            # The file may have been edited outside the app (e.g. by Claude); never overwrite that silently.
            if self.headers.get("If-Match") != etag(current):
                self._send(409, current, "application/json; charset=utf-8", etag(current))
                return
            raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            tmp = CARS_PATH.with_suffix(".json.tmp")
            tmp.write_bytes(raw)
            tmp.replace(CARS_PATH)
        self._send(200, raw, "application/json; charset=utf-8", etag(raw))

    def _host_ok(self) -> bool:
        if self.headers.get("Host") in ALLOWED_HOSTS:
            return True
        self._send(403, b"Forbidden", "text/plain; charset=utf-8")
        return False

    def _send(self, status: int, body: bytes, content_type: str, tag: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if tag:
            self.send_header("ETag", tag)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass  # keep the console quiet


def main(open_browser: bool) -> None:
    if not CARS_PATH.exists():
        build_v40.build()
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        print(f"Port {PORT} is busy - the app is probably already running. Opening {URL}")
        if open_browser:
            webbrowser.open(URL)
        return
    print(f"Car comparison running at {URL}  (close this window or press Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.5, webbrowser.open, args=(URL,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main(open_browser="--no-browser" not in sys.argv)
