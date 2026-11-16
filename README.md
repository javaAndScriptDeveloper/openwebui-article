# Open WebUI for a small team: compose file + API client + one Function

Companion code for **[Self-Hosting Open WebUI for a Backend Team](https://codewithkyryl.dev/2026/11/15/self-hosting-open-webui/)** on codewithkyryl.dev.

## How do I run this?

```bash
cp .env.example .env          # set WEBUI_SECRET_KEY: openssl rand -hex 32
docker compose up -d          # UI: http://127.0.0.1:3000 (loopback only by default)
```

First account created becomes admin; later sign-ups wait for approval
(`DEFAULT_USER_ROLE=pending`, which is also Open WebUI's default). The compose
file pins an Open WebUI release (`OPEN_WEBUI_VERSION`, default `v0.13.3`) and
wires the bundled Ollama service via `OLLAMA_BASE_URL`. To use any
OpenAI-compatible backend (vLLM, LiteLLM, a hosted API) instead, drop the
`ollama` service and its `depends_on` and set `OPENAI_API_BASE_URL` /
`OPENAI_API_KEY`. The port is bound to `127.0.0.1`; for a team, put a
TLS-terminating reverse proxy in front or set `OPEN_WEBUI_BIND`.

The API client (standard library only):

```bash
python client/smoke_test.py               # offline, against the stub
OPENWEBUI_URL=http://localhost:3000 \
OPENWEBUI_API_KEY=sk-... python client/smoke_test.py    # against your instance
python functions/test_date_guardrail_filter.py          # needs pydantic
```

API keys are **off by default** (`ENABLE_API_KEYS`): enable them in
Admin Settings > Authentication (or via the env var, which seeds the setting on
first boot only), then create a key in Settings > Account. Non-admin users also
need the API Keys feature permission.

## What was verified, and how

- `docker compose config` validates the compose file (interpolation, the
  required `WEBUI_SECRET_KEY`). **The stack was not started**: no Open WebUI
  container was run and nothing here was exercised against a live instance.
- `client/smoke_test.py` runs the client against `client/stub_server.py`, an
  offline stand-in whose response shapes follow the Open WebUI source
  (`routers/files.py`, `routers/knowledge.py`) and docs. It checks request
  shapes, multipart upload integrity, the upload -> poll processing status ->
  attach-to-knowledge sequence (the real server rejects attaching an unprocessed
  file), retry on 503, and 401 handling. It runs no model.
- `functions/test_date_guardrail_filter.py` exercises the Filter class directly
  (inlet date injection, outlet logging). It has not been loaded into Open WebUI.

## Files

```
docker-compose.yml          team deployment (open-webui + optional ollama)
.env.example                WEBUI_SECRET_KEY and friends
client/openwebui_client.py  stdlib API client (models/chat/files/status/knowledge)
client/stub_server.py       offline stub of the same endpoints
client/smoke_test.py        runs client vs stub (or vs real instance)
functions/date_guardrail_filter.py       server-side Filter example
functions/test_date_guardrail_filter.py  offline test for it
```

## License

MIT
