"""Local stand-in for the Open WebUI API, standard library only.

Started by smoke_test.py when no OPENWEBUI_URL is set. It answers the four
endpoints the client uses with canned, correctly-shaped responses and enforces
Bearer auth — enough to verify request shapes, parsing, and auth handling
offline. It does not run any model.
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

    def do_GET(self):
        if not self._authed():
            return self._json(401, {"detail": "Invalid API key"})
        if self.path == "/api/models":
            return self._json(200, MODELS)
        if self.path == "/health":
            return self._json(200, {"status": True})
        return self._json(404, {"detail": "Not Found"})

    def do_POST(self):
        if not self._authed():
            return self._json(401, {"detail": "Invalid API key"})
        body = self._read_body()

        if self.path == "/api/chat/completions":
            req = json.loads(body)
            assert req.get("model") and req.get("messages"), "bad request shape"
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
            m = re.search(r'filename="([^"]+)"', body.decode(errors="replace"))
            return self._json(200, {
                "id": "file-stub-001", "filename": m.group(1) if m else "upload.txt",
                "status": "completed",
            })

        m = re.fullmatch(r"/api/v1/knowledge/([^/]+)/file/add", self.path)
        if m:
            req = json.loads(body)
            return self._json(200, {
                "id": m.group(1), "name": f"knowledge-{m.group(1)}",
                "file_ids": [req["file_id"]],
            })

        return self._json(404, {"detail": "Not Found"})


def serve(port: int = 8199) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), StubHandler)
    import threading
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    print(f"stub Open WebUI on http://127.0.0.1:8199 (api key: {API_KEY})")
    ThreadingHTTPServer(("127.0.0.1", 8199), StubHandler).serve_forever()
