"""Offline test for the Filter class. Needs pydantic (Open WebUI ships it).

    python functions/test_date_guardrail_filter.py
"""

import asyncio
import logging
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))

from date_guardrail_filter import Filter  # noqa: E402

TODAY = date.today().isoformat()


def test_inlet_inserts_system_message():
    body = {"messages": [{"role": "user", "content": "what day is it?"}]}
    out = asyncio.run(Filter().inlet(body))
    assert out["messages"][0] == {"role": "system", "content": f"Today's date is {TODAY}."}
    assert out["messages"][1]["role"] == "user" and len(out["messages"]) == 2


def test_inlet_extends_existing_system_message_once():
    f = Filter()
    body = {"messages": [{"role": "system", "content": "Be terse."},
                         {"role": "user", "content": "hi"}]}
    out = asyncio.run(f.inlet(asyncio.run(f.inlet(body))))  # applied twice
    system = [m for m in out["messages"] if m["role"] == "system"]
    assert len(system) == 1, system
    assert system[0]["content"].startswith("Be terse.")
    assert system[0]["content"].count(TODAY) == 1


def test_inlet_respects_valve():
    f = Filter()
    f.valves.inject_date = False
    body = {"messages": [{"role": "user", "content": "hi"}]}
    assert asyncio.run(f.inlet(body))["messages"] == [{"role": "user", "content": "hi"}]


def test_outlet_logs_truncation_without_content_and_does_not_edit(caplog=None):
    records = []

    class H(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    logger = logging.getLogger("date_guardrail_filter")
    logger.addHandler(H())
    body = {"chat_id": "c1", "messages": [
        {"role": "user", "content": "secret question"},
        {"role": "assistant", "content": "secret ans", "finish_reason": "length"}]}
    snapshot = repr(body)
    out = asyncio.run(Filter().outlet(body, {"id": "u1", "email": "a@b.c"}))
    assert repr(out) == snapshot, "outlet must not modify the reply"
    assert len(records) == 1 and "u1" in records[0] and "c1" in records[0], records
    assert "secret" not in records[0] and "a@b.c" not in records[0]


def test_outlet_silent_on_normal_reply():
    records = []

    class H(logging.Handler):
        def emit(self, record):
            records.append(record)

    logging.getLogger("date_guardrail_filter").addHandler(H())
    body = {"messages": [{"role": "assistant", "content": "ok", "finish_reason": "stop"}]}
    asyncio.run(Filter().outlet(body))
    assert not records


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"OK  {name}")
    print("\nAll filter tests passed.")
