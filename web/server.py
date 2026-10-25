"""Local server: API and the Vite site.

  python web/server.py

Every visitor page comes from web/spa. CSV downloads stay in web/data.
Default: http://127.0.0.1:8765/
"""

from __future__ import annotations

import json
import mimetypes
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

WEB = Path(__file__).resolve().parent
SPA = WEB / "spa"
ROOT = WEB.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.api import desk, end_session, get_session, public_session, start_session  # noqa: E402

HOST = "127.0.0.1"
PORT = 8765
COOKIE = "aetheris"
SPA_EXACT = {
    "/",
    "/enter",
    "/desks",
    "/method",
    "/overview",
    "/claims",
    "/backtest",
    "/index.html",
    "/login.html",
    "/overview.html",
    "/claims.html",
    "/backtest.html",
    "/workspaces.html",
    "/for-data.html",
    "/for-insurer.html",
    "/for-reinsurer.html",
    "/for-responder.html",
    "/for-research.html",
    "/for-farmer.html",
}
SPA_PREFIXES = ("/enter", "/desks", "/desk/", "/method", "/claims", "/backtest", "/claim/", "/claim-")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            self._json(200, {"ok": True, "root": str(ROOT), "spa": (SPA / "index.html").exists()})
            return
        if path == "/api/me":
            who = self._who()
            if not who:
                self._json(200, {"ok": False})
                return
            self._json(200, {"ok": True, **public_session(who)})
            return
        if path == "/api/desk":
            try:
                payload = desk()
                who = self._who()
                payload["viewer"] = public_session(who) if who else None
                self._json(200, payload)
            except Exception as err:
                self._json(500, {"ok": False, "error": str(err)})
            return
        if path.startswith("/api/"):
            self._json(404, {"ok": False, "error": "unknown api path"})
            return
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if self._spa_file(path) or self._spa_route(path):
            return
        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/session":
            body = self._body()
            try:
                who = start_session(str(body.get("role") or ""), str(body.get("name") or ""))
            except ValueError:
                self._json(400, {"ok": False, "error": "unknown desk"})
                return
            self._json(
                200,
                {"ok": True, **public_session(who)},
                headers=[("Set-Cookie", self._set_cookie(who["token"]))],
            )
            return
        if path == "/api/logout":
            end_session(self._token())
            self._json(200, {"ok": True}, headers=[("Set-Cookie", self._clear_cookie())])
            return
        if path.startswith("/api/"):
            self._json(404, {"ok": False, "error": "unknown api path"})
            return
        self.send_error(405, "POST is only for /api/session and /api/logout")

    def _spa_route(self, path: str) -> bool:
        if not (SPA / "index.html").exists():
            return False
        if path in SPA_EXACT or path.startswith(SPA_PREFIXES):
            self._send(SPA / "index.html", "text/html; charset=utf-8")
            return True
        return False

    def _spa_file(self, path: str) -> bool:
        if path.startswith("/api/"):
            return False
        rel = path.lstrip("/")
        if not rel:
            return False
        candidate = (SPA / rel).resolve()
        try:
            candidate.relative_to(SPA.resolve())
        except ValueError:
            return False
        if candidate.is_file():
            ctype = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
            self._send(candidate, ctype)
            return True
        return False

    def _send(self, path: Path, content_type: str) -> None:
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        if "html" in content_type or path.suffix in {".js", ".css"}:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _who(self) -> dict | None:
        return get_session(self._token())

    def _token(self) -> str | None:
        raw = self.headers.get("Cookie") or ""
        for part in raw.split(";"):
            if "=" not in part:
                continue
            key, value = part.strip().split("=", 1)
            if key == COOKIE:
                return value
        return None

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _set_cookie(self, token: str) -> str:
        return f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400"

    def _clear_cookie(self) -> str:
        return f"{COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"

    def _json(self, status: int, payload: dict, headers: list[tuple[str, str]] | None = None) -> None:
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        for key, value in headers or []:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)


def main() -> None:
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Aetheris local: http://{HOST}:{PORT}/", flush=True)
    print("Desks: http://{HOST}:{PORT}/enter".format(HOST=HOST, PORT=PORT), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
