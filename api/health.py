from web.http_json import JsonHandler


class handler(JsonHandler):
    def do_GET(self):
        self._json(200, {"ok": True, "host": "vercel"})
