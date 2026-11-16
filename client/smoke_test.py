"""Smoke test for the client. Offline by default; real instance if you ask.

    python client/smoke_test.py            # against the local stub
    OPENWEBUI_URL=http://localhost:3000 \
    OPENWEBUI_API_KEY=sk-... python client/smoke_test.py   # against the real thing

Against the stub it also checks retry and polling behaviour. Those checks need
the stub's fault injection, so they are skipped against a real instance.
The stub's response shapes follow the Open WebUI source; nothing here has been
run against a live Open WebUI instance.
"""

import os
import sys
import urllib.error

sys.path.insert(0, os.path.dirname(__file__))

from openwebui_client import OpenWebUIClient, upload_and_attach  # noqa: E402
from stub_server import API_KEY, STATE, serve  # noqa: E402

RUNBOOK = b"incident runbook: restart pod-a first\n\xc3\xa9 unicode and\r\nCRLF survive"


def expect_http_error(code, fn):
    try:
        fn()
    except urllib.error.HTTPError as e:
        assert e.code == code, f"expected HTTP {code}, got {e.code}"
        return
    raise AssertionError(f"expected HTTP {code}, call succeeded")


def main():
    stub = None
    if url := os.environ.get("OPENWEBUI_URL"):
        base, key = url, os.environ["OPENWEBUI_API_KEY"]
        print(f"running against REAL instance {base}")
    else:
        stub = serve()
        base, key = f"http://127.0.0.1:{stub.server_address[1]}", API_KEY
        print("running against local STUB (set OPENWEBUI_URL for the real thing)")

    client = OpenWebUIClient(base_url=base, api_key=key)

    models = client.models()
    assert any("id" in m for m in models), models
    print(f"OK  models: {[m['id'] for m in models]}")

    answer = client.chat(models[0]["id"], "ping from the smoke test")
    assert answer, "empty completion"
    print(f"OK  chat: {answer[:60]}")

    # the file travels as multipart; against the stub we can check it arrived intact
    upload = client.upload_file("runbook.txt", RUNBOOK)
    assert upload["id"], upload
    if stub:
        stored = STATE["files"][upload["id"]]
        assert stored["filename"] == "runbook.txt", stored["filename"]
        assert stored["content"] == RUNBOOK, stored["content"]
    print(f"OK  file upload: {upload['id']} ({upload.get('filename')})")

    if stub:
        # attaching before processing finished is rejected, like the real server
        expect_http_error(400, lambda: client.add_to_knowledge("kb-runbooks", upload["id"]))
        print("OK  attach before processing finished is rejected (400)")

    kb = upload_and_attach(client, "kb-runbooks", "runbook.txt", RUNBOOK, interval=0.05)
    assert kb.get("id"), kb
    if stub:
        assert "file-stub-001" in kb["file_ids"], kb
    print(f"OK  upload -> wait for processing -> knowledge add: {kb['id']}")

    if stub:
        STATE["fail_next"] = 2
        before = STATE["requests"]
        assert client.models(), "no models after transient 503s"
        assert STATE["requests"] - before == 3, "expected 2 failed attempts + 1 success"
        print("OK  retry: two 503s then success (3 requests)")

        STATE["fail_next"] = 3
        expect_http_error(503, client.models)
        STATE["fail_next"] = 0
        print("OK  retry gives up after 3 attempts and raises the 503")

    # auth actually enforced
    expect_http_error(401, OpenWebUIClient(base_url=base, api_key="sk-wrong").models)
    print("OK  bad API key rejected (401)")

    print("\nAll smoke checks passed.")


if __name__ == "__main__":
    main()
