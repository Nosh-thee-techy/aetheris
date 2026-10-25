"""The data-desk API must repeat the repository files, not invent readings."""

from __future__ import annotations

import json
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from backtest.pipeline.rainfall import published_total
from web.api import ROLES, desk, start_session
from web.server import Handler

SPA = Path(__file__).resolve().parent / "spa" / "index.html"


class DeskTests(unittest.TestCase):
    def test_desk_matches_the_files(self):
        payload = desk()
        self.assertEqual(payload["rainfall"]["mm"], round(published_total(), 1))
        self.assertEqual(payload["rainfall"]["signed"], 7)
        self.assertEqual(payload["radar"]["signed"], 1)
        self.assertEqual(payload["radar"]["below"], 3)
        self.assertEqual(payload["radar"]["no_geometry"], 3)
        self.assertEqual(len(payload["places"]), 7)
        self.assertNotRegex(json.dumps(payload), r"(?i)\baccuracy of \d")
        kabonyo = next(p for p in payload["places"] if p["slug"] == "kabonyo-kanyagwal")
        self.assertEqual(kabonyo["radar"], "yes")
        self.assertTrue(kabonyo["has_outline"])
        self.assertEqual(kabonyo["both"], "yes")
        self.assertIsNotNone(kabonyo["zone"])
        self.assertEqual(kabonyo["zone"]["west"], kabonyo["zone"]["min_lon"])
        kadibo = next(p for p in payload["places"] if p["slug"] == "kadibo")
        self.assertFalse(kadibo["has_outline"])
        self.assertIsNone(kadibo["fraction"])
        self.assertIsNone(kadibo["zone"])
        self.assertTrue(any(m["slug"] == "kadibo" for m in payload["miss"]))
        self.assertEqual(kabonyo["outcome"], "Claim opens")
        self.assertTrue(kabonyo["claim_id"].startswith("0x"))
        self.assertEqual(payload["counts"]["rules"]["radar_plus_rainfall"]["hits"], 1)
        self.assertEqual(payload["chain"]["chain_id"], 11155111)

    def test_known_desks_have_homes(self):
        self.assertEqual(ROLES["icpac"]["home"], "/desk/data")
        self.assertEqual(ROLES["kenya-met"]["home"], "/desk/data")
        self.assertEqual(ROLES["data"]["home"], "/desk/data")
        self.assertEqual(ROLES["insurer"]["home"], "/desk/insurer")
        with self.assertRaises(ValueError):
            start_session("hacker")


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def _open(self, path: str, method: str = "GET", body: dict | None = None, cookie: str | None = None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        if cookie:
            req.add_header("Cookie", cookie)
        return urlopen(req, timeout=5)

    def test_health_and_desk_are_public(self):
        with self._open("/api/health") as res:
            self.assertEqual(res.status, 200)
            self.assertTrue(json.load(res)["ok"])
        with self._open("/api/desk") as res:
            self.assertEqual(res.status, 200)
            payload = json.load(res)
        self.assertEqual(len(payload["places"]), 7)
        self.assertIsNone(payload["viewer"])
        with self._open("/api/me") as res:
            self.assertEqual(res.status, 200)
            self.assertFalse(json.load(res)["ok"])
        with self.assertRaises(HTTPError) as secret:
            self._open("/api/secret")
        self.assertEqual(secret.exception.code, 404)

    def test_session_opens_the_data_desk(self):
        with self._open("/api/session", "POST", {"role": "icpac", "name": "Amina"}) as res:
            self.assertEqual(res.status, 200)
            who = json.load(res)
            cookie = res.headers.get("Set-Cookie", "").split(";", 1)[0]
        self.assertEqual(who["role"], "icpac")
        self.assertEqual(who["home"], "/desk/data")
        self.assertEqual(who["name"], "Amina")
        self.assertEqual(who["role_label"], "ICPAC")
        self.assertNotIn("token", who)
        self.assertTrue(cookie.startswith("aetheris="))
        with self._open("/api/me", cookie=cookie) as res:
            me = json.load(res)
        self.assertEqual(me["label"], "ICPAC")
        self.assertTrue(me["ok"])
        with self._open("/api/desk", cookie=cookie) as res:
            payload = json.load(res)
        self.assertEqual(len(payload["places"]), 7)
        self.assertEqual(payload["viewer"]["role"], "icpac")
        with self.assertRaises(HTTPError) as bad:
            self._open("/api/session", "POST", {"role": "hacker"})
        self.assertEqual(bad.exception.code, 400)

    def test_spa_is_the_door(self):
        if not SPA.exists():
            self.skipTest("run npm run build in app/")
        with self._open("/") as res:
            home = res.read().decode("utf-8")
        self.assertIn('id="app"', home)
        self.assertNotIn("app.js", home)
        with self._open("/enter") as res:
            self.assertIn('id="app"', res.read().decode("utf-8"))
        with self._open("/desk/data") as res:
            self.assertIn('id="app"', res.read().decode("utf-8"))
        for path in ("/overview.html", "/claims.html", "/backtest.html", "/claim-kabonyo-kanyagwal.html", "/method", "/claims"):
            with self._open(path) as res:
                html = res.read().decode("utf-8")
            self.assertIn('id="app"', html)
            self.assertNotIn("app.js", html)
        with self._open("/favicon.ico") as res:
            self.assertEqual(res.status, 204)


if __name__ == "__main__":
    unittest.main()
