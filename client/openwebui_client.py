"""Minimal Open WebUI API client — standard library only, like the article.

Covers exactly what a backend integration needs:
  - list models            GET  /api/models
  - chat completion        POST /api/chat/completions   (OpenAI-compatible)
  - upload a file          POST /api/v1/files/          (multipart)
  - add file to knowledge  POST /api/v1/knowledge/{id}/file/add

Auth: an API key created in Settings > Account (requires ENABLE_API_KEYS).
Sent as `Authorization: Bearer sk-...`.

Point it at a real instance with OPENWEBUI_URL + OPENWEBUI_API_KEY, or at the
stub: smoke_test.py starts client/stub_server.py locally for offline runs.
"""

import json
import os
import time
import urllib.error
import urllib.request
import uuid


class OpenWebUIClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _request(self, method: str, path: str, body: dict | None = None,
                 raw: bytes | None = None, content_type: str | None = None) -> dict:
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        elif raw is not None:
            data = raw
            headers["Content-Type"] = content_type or "application/octet-stream"

        last_error = None
        for attempt in range(3):  # brief retry on 429/5xx, like any polite client
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                if e.code in (429, 502, 503) and attempt < 2:
                    last_error = e
                    time.sleep(1.5 ** attempt)
                    continue
                raise
            except urllib.error.URLError as e:
                raise ConnectionError(f"cannot reach {url}: {e.reason}") from e
        raise last_error

    # -- endpoints ------------------------------------------------------------

    def models(self) -> list[dict]:
        return self._request("GET", "/api/models").get("data", [])

    def chat(self, model: str, message: str) -> str:
        body = {
            "model": model,
            "messages": [{"role": "user", "content": message}],
        }
        out = self._request("POST", "/api/chat/completions", body=body)
        return out["choices"][0]["message"]["content"]

    def upload_file(self, filename: str, content: bytes) -> dict:
        """Multipart upload — /api/v1/files/ processes the file into the vector store."""
        boundary = uuid.uuid4().hex
        part = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: text/plain\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        return self._request(
            "POST", "/api/v1/files/", raw=part,
            content_type=f"multipart/form-data; boundary={boundary}",
        )

    def add_to_knowledge(self, knowledge_id: str, file_id: str) -> dict:
        return self._request(
            "POST",
            f"/api/v1/knowledge/{knowledge_id}/file/add",
            body={"file_id": file_id},
        )


def client_from_env() -> OpenWebUIClient:
    return OpenWebUIClient(
        base_url=os.environ.get("OPENWEBUI_URL", "http://localhost:3000"),
        api_key=os.environ["OPENWEBUI_API_KEY"],
    )
