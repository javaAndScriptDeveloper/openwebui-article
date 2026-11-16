"""An Open WebUI Filter Function: date injection plus truncation logging.

Paste this whole file into Admin Panel > Functions > New Function (Functions
run server-side as arbitrary Python; creating them is admin-only by design).

What it does:
- inlet: adds today's date to the system prompt, so the model stops falling
  back to its training cutoff when asked about "today". The date is the
  SERVER's local date (UTC in a stock container), not the user's.
- outlet: logs a line when a reply was cut off by the token limit
  (finish_reason == "length"). Metadata only, no message content, no email.
  Outlet is the place for logging; edits made there are not returned to API
  callers, so this filter does not rewrite replies.

Structure follows the Filter contract in the Open WebUI docs
(inlet/outlet + Valves). It has not been loaded into a live Open WebUI
instance; functions/test_date_guardrail_filter.py exercises the class directly.
"""

import logging
from datetime import date

from pydantic import BaseModel

log = logging.getLogger(__name__)


class Filter:
    class Valves(BaseModel):
        inject_date: bool = True
        log_truncation: bool = True

    def __init__(self):
        self.valves = self.Valves()

    async def inlet(self, body: dict, __user__: dict | None = None) -> dict:
        if not self.valves.inject_date:
            return body
        note = f"Today's date is {date.today().isoformat()}."
        messages = body.setdefault("messages", [])
        if messages and messages[0].get("role") == "system":
            first = messages[0]
            if note not in str(first.get("content", "")):
                first["content"] = f"{first.get('content', '')}\n\n{note}".strip()
        else:
            messages.insert(0, {"role": "system", "content": note})
        return body

    async def outlet(self, body: dict, __user__: dict | None = None) -> dict:
        if self.valves.log_truncation:
            messages = body.get("messages") or []
            last = messages[-1] if messages else {}
            if last.get("role") == "assistant" and last.get("finish_reason") == "length":
                log.warning(
                    "reply truncated by token limit: user_id=%s chat_id=%s",
                    (__user__ or {}).get("id"), body.get("chat_id"),
                )
        return body
