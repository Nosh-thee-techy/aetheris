from web.http_json import JsonHandler
from web.api import desk, get_session, public_session


class handler(JsonHandler):
    def do_GET(self):
        try:
            payload = desk()
            who = get_session(self._token())
            payload["viewer"] = public_session(who) if who else None
            self._json(200, payload)
        except Exception as err:
            self._json(500, {"ok": False, "error": str(err)})
