"""Smoke test for the client. Offline by default; real instance if you ask.

    uv run python smoke_test.py            # against the local stub
    OPENWEBUI_URL=http://localhost:3000 \
    OPENWEBUI_API_KEY=sk-... uv run python smoke_test.py   # against the real thing
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from openwebui_client import OpenWebUIClient  # noqa: E402
from stub_server import API_KEY, serve  # noqa: E402


def main():
    if url := os.environ.get("OPENWEBUI_URL"):
        base, key = url, os.environ["OPENWEBUI_API_KEY"]
        print(f"running against REAL instance {base}")
    else:
        serve()
        base, key = "http://127.0.0.1:8199", API_KEY
        print("running against local STUB (set OPENWEBUI_URL for the real thing)")

    client = OpenWebUIClient(base_url=base, api_key=key)

    models = client.models()
    assert any("id" in m for m in models), models
    print(f"OK  models: {[m['id'] for m in models]}")

    answer = client.chat(models[0]["id"], "ping from the smoke test")
    assert answer, "empty completion"
    print(f"OK  chat: {answer[:60]}")

    upload = client.upload_file("runbook.txt", b"incident runbook: restart pod-a first")
    assert upload["id"], upload
    print(f"OK  file upload: {upload['id']} ({upload.get('filename')})")

    kb = client.add_to_knowledge("kb-runbooks", upload["id"])
    assert upload["id"] in kb.get("file_ids", [])
    print(f"OK  knowledge add: {kb['id']} <- {upload['id']}")

    # auth actually enforced
    try:
        OpenWebUIClient(base_url=base, api_key="sk-wrong").models()
        raise AssertionError("bad key accepted")
    except Exception as e:
        assert "401" in str(e) or "Invalid" in str(e), e
        print("OK  bad API key rejected (401)")

    print("\nAll smoke checks passed.")


if __name__ == "__main__":
    main()
