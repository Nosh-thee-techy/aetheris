from web.http_json import JsonHandler
from web.api import public_session, start_session


class handler(JsonHandler):
    def do_POST(self):
        body = self._body()
        try:
            who = start_session(str(body.get("role") or ""), str(body.get("name") or ""))
        except ValueError:
            self._json(400, {"ok": False, "error": "unknown desk"})
            return
        self._json(200, {"ok": True, **public_session(who)}, headers=[("Set-Cookie", self._set_cookie(who["token"]))])
