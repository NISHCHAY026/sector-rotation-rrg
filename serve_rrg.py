# Live RRG server.
#   py -3.11 serve_rrg.py            -> serves http://localhost:8787 and opens it
#   py -3.11 serve_rrg.py --port 9000 --no-open
#
# The page fetches /data.json on load and polls it every 60s, so the
# dashboard updates itself while you leave the tab open. Market data is
# re-pulled from yfinance at most once per TTL (default 90s) to stay fast
# and avoid rate limits. The last good payload is always kept as a fallback.

import argparse
import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import generate_rrg as g

TTL = 90  # seconds between live yfinance refreshes
_lock = threading.Lock()
_cache = {"data": None, "ts": 0.0}


def get_data():
    now = time.time()
    with _lock:
        fresh = _cache["data"] is not None and (now - _cache["ts"]) < TTL
        if fresh:
            return _cache["data"]
    try:
        data = g.build_payload()
        with _lock:
            _cache["data"] = data
            _cache["ts"] = time.time()
        return data
    except Exception as e:                       # network hiccup / rate limit
        if _cache["data"] is not None:
            print(f"[warn] refresh failed ({e}); serving cached data")
            return _cache["data"]
        raise


def render_page():
    data = get_data()
    tpl = (g.HERE / "rrg_template.html").read_text(encoding="utf-8")
    return (tpl.replace("__DATA__", json.dumps(data))
               .replace("__LIVE__", "true"))


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, ctype: str):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        try:
            if path in ("/", "/index.html", "/rrg_live.html"):
                self._send(render_page().encode("utf-8"),
                           "text/html; charset=utf-8")
            elif path in ("/data.json", "/data"):
                self._send(json.dumps(get_data()).encode("utf-8"),
                           "application/json")
            else:
                self.send_error(404)
        except BrokenPipeError:
            pass
        except Exception as e:
            self.send_error(500, str(e))

    def log_message(self, *_):                   # quiet console
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    url = f"http://localhost:{args.port}/"
    print(f"Sector rotation RRG -> {url}")
    print("Warming up (pulling market data)...")
    get_data()                                   # prime the cache before serving
    print(f"Ready. Live, refreshes every {TTL}s. Ctrl+C to stop.")

    if not args.no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
