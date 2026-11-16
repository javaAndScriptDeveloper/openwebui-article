"""Minimal Open WebUI API client — standard library only, like the article.

Covers exactly what a backend integration needs:
  - list models            GET  /api/models
  - chat completion        POST /api/chat/completions   (OpenAI-compatible)
  - upload a file          POST /api/v1/files/          (multipart)
  - file processing status GET  /api/v1/files/{id}/process/status
  - add file to knowledge  POST /api/v1/knowledge/{id}/file/add

Uploads are processed (parsed, embedded) in the background by default, and
adding a file to a knowledge base before that finishes is rejected by the
server, so upload_and_attach() polls the status endpoint in between.

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
        for attempt in range(3):  # brief retry on 429/502/503; other errors are raised as-is
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

    def upload_file(self, filename: str, content: bytes,
                    content_type: str = "text/plain") -> dict:
        """Multipart upload. The server starts processing in the background; poll
        wait_until_processed() before attaching the file to a knowledge base."""
        boundary = uuid.uuid4().hex
        part = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        return self._request(
            "POST", "/api/v1/files/", raw=part,
            content_type=f"multipart/form-data; boundary={boundary}",
        )

    def wait_until_processed(self, file_id: str, timeout: float = 120.0,
                             interval: float = 1.0) -> dict:
        """Poll until the server reports the file as completed (or failed)."""
        deadline = time.monotonic() + timeout
        while True:
            status = self._request("GET", f"/api/v1/files/{file_id}/process/status")
            state = status.get("status")
            if state == "completed":
                return status
            if state == "failed":
                raise RuntimeError(f"file {file_id} failed processing: {status.get('error')}")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"file {file_id} still '{state}' after {timeout}s")
            time.sleep(interval)

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


def upload_and_attach(client: OpenWebUIClient, knowledge_id: str, filename: str,
                      content: bytes, **poll) -> dict:
    """Upload, wait for processing, attach to a knowledge base."""
    uploaded = client.upload_file(filename, content)
    client.wait_until_processed(uploaded["id"], **poll)
    return client.add_to_knowledge(knowledge_id, uploaded["id"])
