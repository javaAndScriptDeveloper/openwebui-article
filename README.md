# Open WebUI for a small team: compose file + API client + one Function

Companion code for **[Self-Hosting Open WebUI for a Backend Team](https://codewithkyryl.dev/2026/11/15/self-hosting-open-webui/)** on codewithkyryl.dev.

## How do I run this?

```bash
cp .env.example .env          # set WEBUI_SECRET_KEY: openssl rand -hex 32
docker compose up -d          # UI: http://localhost:3000
```

First account created becomes admin; later sign-ups wait for approval
(`DEFAULT_USER_ROLE=pending`). Models come from Ollama (bundled service),
or set `OPENAI_API_BASE_URL`/`OPENAI_API_KEY` to point at vLLM/LiteLLM/anything
OpenAI-compatible — Open WebUI is not tied to Ollama.

The API client (standard library only):

```bash
python client/smoke_test.py               # offline, against the stub
OPENWEBUI_URL=http://localhost:3000 \
OPENWEBUI_API_KEY=sk-... python client/smoke_test.py    # against your instance
```

API keys are **off by default** (`ENABLE_API_KEYS`): enable them in
Settings > Authentication, then create a key in Settings > Account.

## What is real and what is a stub

- `docker-compose.yml` is a real deployment: pinned volume, `WEBUI_SECRET_KEY`,
  extra_hosts for host Ollama, API keys enabled, pending-user signups.
- `client/openwebui_client.py` is the real integration: models, chat
  completions (OpenAI-compatible), file upload (multipart), knowledge add —
  with auth and retry-on-429/5xx.
- `client/stub_server.py` is a local stand-in answering those four endpoints
  with canned, correctly-shaped responses. `smoke_test.py` uses it when
  `OPENWEBUI_URL` is unset: request shapes, parsing, and auth handling all
  verified offline. It runs no model.
- `functions/date_guardrail_filter.py` is a real Open WebUI Filter (inlet +
  outlet + Valves) — paste into Workspace > Functions. Not executed by the
  smoke test.

## Files

```
docker-compose.yml          team deployment (open-webui + optional ollama)
.env.example                WEBUI_SECRET_KEY and friends
client/openwebui_client.py  stdlib API client (models/chat/files/knowledge)
client/stub_server.py       offline stub of the same endpoints
client/smoke_test.py        runs client vs stub (or vs real instance)
functions/date_guardrail_filter.py  server-side Filter example
```

## License

MIT
