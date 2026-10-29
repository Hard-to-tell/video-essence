"""界面的本地服务器：提供 app/web 下的静态页面，并把 /api/* 交给 API 表。

backend 提供真实任务队列；只有显式 ?mock=1 才加载演示数据。

用法：python app/server.py [--port 8765] [--no-open]
"""
import argparse
import json
import re
import sys
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB = Path(__file__).resolve().parent / "web"

# (方法, 路径正则) -> handler(match, body) -> 可 JSON 序列化的对象
# 处理函数抛出 ApiError 时按其 status 返回 {"message": ...}。
API = {}


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def route(method, pattern):
    def deco(fn):
        API[(method, re.compile(pattern))] = fn
        return fn
    return deco


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(WEB), **kw)

    def log_message(self, fmt, *args):
        pass

    def _api(self, method):
        path = self.path.split("?", 1)[0]
        origin = self.headers.get('Origin')
        host = self.headers.get('Host','')
        if host not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'):
            return self._json(403, {'message':'仅允许本机访问'})
        if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
            return self._json(403, {'message':'拒绝跨站请求'})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if not 0<=length<=1048576:
                return self._json(413, {'message':'请求过大'})
            body = json.loads(self.rfile.read(length) or b"{}") if length else {}
            if not isinstance(body,dict): raise ValueError()
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {'message':'请求必须是JSON对象'})
        for (m, pattern), fn in API.items():
            match = m == method and pattern.fullmatch(path)
            if match:
                try:
                    return self._json(200, fn(match, body))
                except ApiError as exc:
                    return self._json(exc.status, {"message": str(exc)})
                except ValueError as exc:
                    return self._json(400, {"message": str(exc)})
                except Exception as exc:  # 不让单个请求拖垮服务器
                    return self._json(500, {"message": f"后端出错：{exc}"})
        self._json(501, {"message": "后端还没实现这个接口"})

    def _json(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._api("GET")
        super().do_GET()

    def do_POST(self):
        self._api("POST")

    def do_PUT(self):
        self._api("PUT")

    def end_headers(self):
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    from backend import register
    register(route, ApiError)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"界面已启动：{url}（关闭这个窗口即退出）", file=sys.stderr)
    if not args.no_open:
        threading.Timer(0.5, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
