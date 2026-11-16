"""Local stand-in for the Open WebUI API, standard library only.

Started by smoke_test.py when no OPENWEBUI_URL is set. It answers the endpoints
the client uses with canned, correctly-shaped responses and enforces Bearer
auth: enough to verify request shapes, multipart encoding, polling, retry and
auth handling offline. It does not run any model, and its response shapes are
modelled on the Open WebUI source, not recorded from a live instance.
"""

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_KEY = "sk-stub-0123456789abcdef0123456789abcdef"

MODELS = {
    "data": [
        {"id": "qwen3:8b", "object": "model", "owned_by": "ollama"},
        {"id": "gpt-4o-mini", "object": "model", "owned_by": "openai"},
    ]
}


# Mutable knobs the smoke test flips to exercise client behaviour.
STATE = {
    "fail_next": 0,        # answer the next N authorised requests with 503
    "requests": 0,         # authorised requests seen (to count retries)
    "status_polls": 0,     # polls of the file status endpoint
    "polls_until_done": 2, # status endpoint says "pending" this many times first
    "files": {},           # file_id -> {"filename", "content"}
}


def parse_multipart(content_type: str, body: bytes) -> tuple[str, bytes]:
    """Return (filename, file bytes) from a single-part multipart/form-data body."""
    m = re.search(r"boundary=([^;]+)", content_type)
    assert m, f"no boundary in {content_type!r}"
    boundary = b"--" + m.group(1).encode()
    part = body.split(boundary)[1]
    head, _, rest = part.partition(b"\r\n\r\n")
    filename = re.search(rb'filename="([^"]+)"', head).group(1).decode()
    return filename, rest.removesuffix(b"\r\n")


class StubHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _authed(self) -> bool:
        header = self.headers.get("Authorization", "")
        return header == f"Bearer {API_KEY}"

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    def _flaky(self) -> bool:
        STATE["requests"] += 1
        if STATE["fail_next"] > 0:
            STATE["fail_next"] -= 1
            self._json(503, {"detail": "Service Unavailable"})
            return True
        return False

    def do_GET(self):
        if not self._authed():
            return self._json(401, {"detail": "Invalid API key"})
        if self._flaky():
            return
        if self.path == "/api/models":
            return self._json(200, MODELS)
        m = re.fullmatch(r"/api/v1/files/([^/]+)/process/status", self.path)
        if m:
            if m.group(1) not in STATE["files"]:
                return self._json(404, {"detail": "Not Found"})
            STATE["status_polls"] += 1
            done = STATE["status_polls"] > STATE["polls_until_done"]
            return self._json(200, {"status": "completed" if done else "pending"})
        if self.path == "/health":
            return self._json(200, {"status": True})
        return self._json(404, {"detail": "Not Found"})

    def do_POST(self):
        if not self._authed():
            return self._json(401, {"detail": "Invalid API key"})
        if self._flaky():
            return
        body = self._read_body()

        if self.path == "/api/chat/completions":
            req = json.loads(body)
            if not (req.get("model") and req.get("messages")):
                return self._json(422, {"detail": "bad request shape"})
            user_msg = req["messages"][-1]["content"]
            return self._json(200, {
                "id": "chatcmpl-stub",
                "object": "chat.completion",
                "model": req["model"],
                "choices": [{
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": f"stub reply to: {user_msg[:40]}"},
                }],
            })

        if self.path == "/api/v1/files/":
            filename, content = parse_multipart(self.headers.get("Content-Type", ""), body)
            STATE["files"]["file-stub-001"] = {"filename": filename, "content": content}
            STATE["status_polls"] = 0
            return self._json(200, {
                "id": "file-stub-001", "filename": filename,
                "meta": {"size": len(content)},
            })

        m = re.fullmatch(r"/api/v1/knowledge/([^/]+)/file/add", self.path)
        if m:
            req = json.loads(body)
            # like the real server: a file that is not processed yet is rejected
            if STATE["status_polls"] <= STATE["polls_until_done"]:
                return self._json(400, {"detail": "File not processed"})
            return self._json(200, {
                "id": m.group(1), "name": f"knowledge-{m.group(1)}",
                "file_ids": [req["file_id"]],
            })

        return self._json(404, {"detail": "Not Found"})


def serve(port: int = 0) -> ThreadingHTTPServer:
    """Start the stub in a daemon thread. port=0 picks a free port: see server.server_address."""
    import threading
    server = ThreadingHTTPServer(("127.0.0.1", port), StubHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    print(f"stub Open WebUI on http://127.0.0.1:8199 (api key: {API_KEY})")
    ThreadingHTTPServer(("127.0.0.1", 8199), StubHandler).serve_forever()
