"""Local review page: play renders, A/B them, and leave comments pinned to time ranges (bars + clips)."""

from __future__ import annotations

import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from glass_harbor import feedback


def _run_dir(slug: str, stamp: str) -> Path:
    if not re.fullmatch(r"[0-9A-Za-z_\-]+", stamp):
        raise ValueError("bad run id")
    for run in feedback.list_runs(slug):
        if run.name == stamp:
            return run
    raise FileNotFoundError(f"No render {stamp} for {slug}")


def make_handler(slug: str) -> type[BaseHTTPRequestHandler]:
    page = resources.files("glass_harbor").joinpath("review.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # quiet server
            return

        def _json(self, payload: Any, status: int = 200) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _error(self, error: Exception) -> None:
            status = HTTPStatus.NOT_FOUND if isinstance(error, (FileNotFoundError, KeyError)) else HTTPStatus.BAD_REQUEST
            self._json({"error": str(error)}, status)

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or 0)
            return json.loads(self.rfile.read(length) or b"{}")

        def _serve_audio(self, path: Path) -> None:
            size = path.stat().st_size
            ctype = "audio/mpeg" if path.suffix == ".mp3" else "audio/wav"
            start, end = 0, size - 1
            match = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
            if match and (match.group(1) or match.group(2)):
                if match.group(1):
                    start = int(match.group(1))
                    end = int(match.group(2)) if match.group(2) else size - 1
                else:
                    start = max(0, size - int(match.group(2)))
                end = min(end, size - 1)
                self.send_response(HTTPStatus.PARTIAL_CONTENT)
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            else:
                self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            with path.open("rb") as handle:
                handle.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    chunk = handle.read(min(1 << 16, remaining))
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        return
                    remaining -= len(chunk)

        def do_GET(self) -> None:  # noqa: N802
            path = unquote(self.path.split("?", 1)[0])
            try:
                if path in ("/", "/index.html"):
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(page)))
                    self.end_headers()
                    self.wfile.write(page)
                elif path == "/api/session":
                    runs = [r.name for r in feedback.list_runs(slug)]
                    if not runs:
                        raise FileNotFoundError(f"No renders for {slug}; run glass-harbor mix render {slug}")
                    self._json({"slug": slug, "runs": runs, "tags": list(feedback.TAGS)})
                elif m := re.fullmatch(r"/api/run/([^/]+)", path):
                    run = _run_dir(slug, m.group(1))
                    self._json({"timeline": feedback.run_timeline(run), "peaks": feedback.peaks(run),
                                "feedback": feedback.load_feedback(run)})
                elif m := re.fullmatch(r"/audio/([^/]+)", path):
                    run = _run_dir(slug, m.group(1))
                    mp3 = run / "mix.mp3"
                    self._serve_audio(mp3 if mp3.exists() else run / "mix.wav")
                else:
                    self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            except Exception as error:  # surface errors to the page
                self._error(error)

        def do_POST(self) -> None:  # noqa: N802
            path = unquote(self.path)
            try:
                body = self._body()
                if m := re.fullmatch(r"/api/run/([^/]+)/comments", path):
                    run = _run_dir(slug, m.group(1))
                    comment = feedback.add_comment(run, time_s=float(body["time_s"]), end_s=body.get("end_s"),
                                                   tag=body.get("tag", "other"), text=str(body.get("text", "")))
                    self._json(comment)
                elif m := re.fullmatch(r"/api/run/([^/]+)/comments/([0-9a-f]+)", path):
                    run = _run_dir(slug, m.group(1))
                    self._json(feedback.set_comment_status(run, m.group(2), body.get("status", "resolved"),
                                                           body.get("note", "")))
                elif m := re.fullmatch(r"/api/run/([^/]+)/verdict", path):
                    run = _run_dir(slug, m.group(1))
                    self._json(feedback.set_verdict(run, slug, body.get("verdict", ""), body.get("note", "")))
                else:
                    self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            except Exception as error:
                self._error(error)

        def do_DELETE(self) -> None:  # noqa: N802
            try:
                if m := re.fullmatch(r"/api/run/([^/]+)/comments/([0-9a-f]+)", unquote(self.path)):
                    feedback.delete_comment(_run_dir(slug, m.group(1)), m.group(2))
                    self._json({"ok": True})
                else:
                    self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            except Exception as error:
                self._error(error)

    return Handler


def serve(slug: str, port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(slug))
