from web.http_json import JsonHandler
from web.api import get_session, public_session


class handler(JsonHandler):
    def do_GET(self):
        who = get_session(self._token())
        if not who:
            self._json(200, {"ok": False})
            return
        self._json(200, {"ok": True, **public_session(who)})
