"""A real Open WebUI Filter Function: production guardrails on every chat.

Paste this whole file into Workspace > Functions > New Function in the admin
UI (Functions run server-side; creating them is admin-only by design —
arbitrary Python execution).

What it does:
- inlet: injects a dated system note so the model stops answering
  "as of my knowledge cutoff" for things like "what's today".
- outlet: stamps every response with a visible tag, so logs and screenshots
  always show which chats went through the filter.

Structure follows the official Filter contract (inlet/stream/outlet + Valves).
"""

from pydantic import BaseModel


class Filter:
    class Valves(BaseModel):
        tag: str = "filtered"
        inject_date: bool = True

    def __init__(self):
        self.valves = self.Valves()

    async def inlet(self, body: dict, __user__: dict | None = None) -> dict:
        messages = body.get("messages", [])
        if self.valves.inject_date and messages:
            from datetime import date
            messages.insert(0, {
                "role": "system",
                "content": f"Today's date is {date.today().isoformat()}.",
            })
        print(f"[{self.valves.tag}] inlet: user={__user__ and __user__.get('email')}")
        return body

    async def outlet(self, body: dict, __user__: dict | None = None) -> dict:
        messages = body.get("messages", [])
        if messages:
            last = messages[-1]
            last["content"] = f"{last['content']}\n\n_[{self.valves.tag}]_"
        return body
