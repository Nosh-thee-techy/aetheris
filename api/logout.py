from web.http_json import JsonHandler
from web.api import end_session


class handler(JsonHandler):
    def do_POST(self):
        end_session(self._token())
        self._json(200, {"ok": True}, headers=[("Set-Cookie", self._clear_cookie())])
