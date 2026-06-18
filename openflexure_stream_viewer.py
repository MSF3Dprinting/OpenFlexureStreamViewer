#!/usr/bin/env python3
"""Minimal OpenFlexure camera viewer.

This serves a small web page on a separate port on the microscope itself,
proxies the microscope camera MJPEG stream, and saves the current frame on
the microscope storage.
"""

from __future__ import annotations

import argparse
import datetime
import json
import mimetypes
import sys
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
CAPTURE_DIR = BASE_DIR / "captures"
DEFAULT_UPSTREAM = "http://127.0.0.1:5000"


def _send_json(handler: SimpleHTTPRequestHandler, status: HTTPStatus, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=True, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _capture_jpeg_frame(stream: Any) -> bytes:
    buffer = bytearray()

    while True:
        chunk = stream.read(8192)
        if not chunk:
            break

        buffer.extend(chunk)
        start = buffer.find(b"\xff\xd8")
        if start == -1:
            if len(buffer) > 2_000_000:
                del buffer[:-2]
            continue

        if start > 0:
            del buffer[:start]

        end = buffer.find(b"\xff\xd9", 2)
        if end != -1:
            return bytes(buffer[: end + 2])

        if len(buffer) > 2_000_000:
            del buffer[:-2]

    raise RuntimeError("Unable to capture a JPEG frame from the stream.")


class ViewerRequestHandler(SimpleHTTPRequestHandler):
    server_version = "OpenFlexureStreamViewer/1.0"

    def __init__(self, *args: Any, directory: str | None = None, upstream_base: str | None = None, **kwargs: Any) -> None:
        self.upstream_base = (upstream_base or DEFAULT_UPSTREAM).rstrip("/")
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/index.html"}:
            self.path = "/index.html"
            return super().do_GET()

        if self.path == "/healthz":
            return _send_json(self, HTTPStatus.OK, {"ok": True, "upstream": self.upstream_base})

        if self.path == "/camera/mjpeg_stream":
            return self._proxy_mjpeg_stream()

        if self.path == "/capture":
            return self._capture_photo()

        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/capture":
            return self._capture_photo()
        self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")

    def do_HEAD(self) -> None:  # noqa: N802
        if self.path in {"/", "/index.html"}:
            self.path = "/index.html"
        return super().do_HEAD()

    def _proxy_mjpeg_stream(self) -> None:
        upstream_url = urljoin(f"{self.upstream_base}/", "camera/mjpeg_stream")
        request = Request(upstream_url, headers={"User-Agent": self.headers.get("User-Agent", self.server_version)})

        try:
            upstream = urlopen(request, timeout=10)
        except URLError as exc:
            message = {"error": "Unable to connect to the OpenFlexure camera stream.", "detail": str(exc)}
            return _send_json(self, HTTPStatus.BAD_GATEWAY, message)

        self.send_response(HTTPStatus.OK)
        content_type = upstream.headers.get_content_type()
        content_charset = upstream.headers.get_content_charset()
        if content_type == "multipart/x-mixed-replace":
            boundary = upstream.headers.get_param("boundary")
            header_value = "multipart/x-mixed-replace"
            if boundary:
                header_value = f"{header_value}; boundary={boundary}"
            self.send_header("Content-Type", header_value)
        elif content_charset:
            self.send_header("Content-Type", f"{content_type}; charset={content_charset}")
        else:
            self.send_header("Content-Type", upstream.headers.get("Content-Type", "application/octet-stream"))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        try:
            while True:
                chunk = upstream.read(8192)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        finally:
            upstream.close()

    def _capture_photo(self) -> None:
        upstream_url = urljoin(f"{self.upstream_base}/", "camera/mjpeg_stream")
        request = Request(upstream_url, headers={"User-Agent": self.headers.get("User-Agent", self.server_version)})

        try:
            upstream = urlopen(request, timeout=10)
        except URLError as exc:
            message = {"error": "Unable to connect to the OpenFlexure camera stream.", "detail": str(exc)}
            return _send_json(self, HTTPStatus.BAD_GATEWAY, message)

        try:
            frame = _capture_jpeg_frame(upstream)
            CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"openflexure-photo-{timestamp}.jpg"
            capture_path = CAPTURE_DIR / filename
            capture_path.write_bytes(frame)

            return _send_json(
                self,
                HTTPStatus.OK,
                {
                    "ok": True,
                    "filename": filename,
                    "path": str(capture_path),
                    "upstream": self.upstream_base,
                },
            )
        except RuntimeError as exc:
            return _send_json(self, HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
        finally:
            upstream.close()

    def translate_path(self, path: str) -> str:
        if path == "/":
            path = "/index.html"
        if path in {"/index.html", "/style.css", "/app.js"}:
            return str(WEB_DIR / path.lstrip("/"))
        return super().translate_path(path)

    def guess_type(self, path: str) -> str:
        if path.endswith(".js"):
            return "application/javascript"
        if path.endswith(".css"):
            return "text/css"
        if path.endswith(".html"):
            return "text/html"
        return mimetypes.guess_type(path)[0] or "application/octet-stream"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve a lightweight OpenFlexure camera viewer.")
    parser.add_argument("--host", default="0.0.0.0", help="Interface to bind to. Default: 0.0.0.0")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on. Default: 8080")
    parser.add_argument(
        "--capture-dir",
        default=str(CAPTURE_DIR),
        help="Directory used to store captured photos. Default: ./captures",
    )
    parser.add_argument(
        "--upstream",
        default=DEFAULT_UPSTREAM,
        help="Base URL of the main OpenFlexure server. Default: http://127.0.0.1:5000",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    capture_dir = Path(args.capture_dir)
    handler = partial(ViewerRequestHandler, directory=str(WEB_DIR), upstream_base=args.upstream)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    global CAPTURE_DIR
    CAPTURE_DIR = capture_dir
    print(f"Serving the OpenFlexure stream viewer on http://{args.host}:{args.port}")
    print(f"Proxying the camera stream from {args.upstream.rstrip('/')}/camera/mjpeg_stream")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())