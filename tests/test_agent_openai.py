"""The open-source model path: OpenAI-compatible wire format, tested against a local fake server."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace as NS

import pytest

from planner import agent, climate


def test_history_converts_to_openai_messages():
    history = [
        {"role": "user", "content": "What if my budget is half?"},
        {"role": "assistant", "content": [NS(type="thinking", thinking=""), NS(type="text", text="Let me check."),
                                          NS(type="tool_use", id="c1", name="run_plan", input={"lat": 25.0})]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": '{"ok": 1}'}]},
    ]
    out = agent.to_openai_messages("SYS", history)
    assert out[0] == {"role": "system", "content": "SYS"}
    assert out[1] == {"role": "user", "content": "What if my budget is half?"}
    assert out[2]["content"] == "Let me check."
    assert out[2]["tool_calls"][0]["function"] == {"name": "run_plan", "arguments": '{"lat": 25.0}'}
    assert out[3] == {"role": "tool", "tool_call_id": "c1", "content": '{"ok": 1}'}


def test_openai_response_with_tool_call():
    data = {"choices": [{"finish_reason": "tool_calls", "message": {"content": None, "tool_calls": [
        {"id": "x", "type": "function", "function": {"name": "run_plan", "arguments": '{"lat": 1, "lon": 2}'}}]}}]}
    r = agent.from_openai_response(data)
    assert r.stop_reason == "tool_use"
    assert r.content[0].type == "tool_use" and r.content[0].input == {"lat": 1, "lon": 2}


def test_openai_response_text_and_bad_json():
    assert agent.from_openai_response({"choices": [{"finish_reason": "stop", "message": {"content": "Hi"}}]}).stop_reason == "end_turn"
    assert agent.from_openai_response({"choices": [{"finish_reason": "length", "message": {"content": "Hi"}}]}).stop_reason == "max_tokens"
    r = agent.from_openai_response({"choices": [{"message": {"tool_calls": [{"function": {"name": "run_plan", "arguments": "{oops"}}]}}]})
    assert r.content[0].input == {"_invalid_json": "{oops"} and r.content[0].id == "call_0"


class FakeOpenAI(BaseHTTPRequestHandler):
    """Answers the first request with a run_plan tool call, the next ones with text quoting the new plan."""
    requests_seen: list = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOpenAI.requests_seen.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
        tool_msgs = [m for m in body["messages"] if m["role"] == "tool"]
        if not tool_msgs:
            msg = {"content": None, "tool_calls": [{"id": "call_1", "type": "function", "function": {
                "name": "run_plan", "arguments": json.dumps({"lat": 25.0, "lon": 51.0, "area_m2": 500, "budget_qar": 125000, "priority": "profit"})}}]}
            reply = {"choices": [{"finish_reason": "tool_calls", "message": msg}]}
        else:
            plan = json.loads(tool_msgs[-1]["content"])
            capex = plan["recommended"]["capex_qar"] if plan["recommended"] else 0
            reply = {"choices": [{"finish_reason": "stop", "message": {"content": f"With half the budget the build cost is {capex:,.0f} QAR."}}]}
        out = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


@pytest.fixture
def fake_server(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), FakeOpenAI)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    FakeOpenAI.requests_seen = []
    monkeypatch.setattr(agent, "PROVIDER", "openai_compatible")
    monkeypatch.setattr(agent, "MODEL", "qwen2.5:7b-instruct")
    monkeypatch.setattr(agent, "BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    monkeypatch.setattr(agent, "API_KEY", "test-key")
    yield server
    server.shutdown()


def test_full_loop_against_openai_compatible_server(fake_server, monkeypatch, dry_year):
    monkeypatch.setattr(climate, "get_typical_year", lambda lat, lon: dry_year)
    out = agent.ask("What if my budget is half?", [], None)
    assert out["verified"], out
    assert out["plan"]["inputs"]["budget_qar"] == 125000
    assert out["tool_log"][0].startswith("run_plan(")
    first = FakeOpenAI.requests_seen[0]
    assert first["path"] == "/v1/chat/completions" and first["auth"] == "Bearer test-key"
    assert first["body"]["model"] == "qwen2.5:7b-instruct" and first["body"]["temperature"] == 0.0
    assert [x["function"]["name"] for x in first["body"]["tools"]] == ["run_plan", "compare_sites"]


def test_llm_ready(monkeypatch):
    monkeypatch.setattr(agent, "PROVIDER", "openai_compatible")
    assert agent.llm_ready() == (True, "chat_no_base_url")
    monkeypatch.setattr(agent, "PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert agent.llm_ready() == (False, "chat_no_key")
    monkeypatch.setattr(agent, "PROVIDER", "nope")
    assert agent.llm_ready()[0] is False


def test_openrouter_sends_app_headers_and_fallbacks(monkeypatch):
    sent = {}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"finish_reason": "stop", "message": {"content": "ok"}}]}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent.update(url=url, body=json, headers=headers)
        return Resp()

    monkeypatch.setattr(agent, "BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setattr(agent, "MODEL", "qwen/qwen3.8-27b:free")
    monkeypatch.setattr(agent, "FALLBACK_MODELS", ["openrouter/free"])
    monkeypatch.setattr(agent, "API_KEY", "sk-or-test")
    monkeypatch.setattr(agent.requests, "post", fake_post)
    agent._call_openai_compatible("SYS", [{"role": "user", "content": "hi"}], agent.TOOLS, None)
    assert sent["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert sent["headers"]["Authorization"] == "Bearer sk-or-test" and sent["headers"]["X-Title"] == "Croptions"
    assert sent["body"]["models"] == ["qwen/qwen3.8-27b:free", "openrouter/free"]


def test_openrouter_without_key_is_not_ready(monkeypatch):
    monkeypatch.setattr(agent, "PROVIDER", "openai_compatible")
    monkeypatch.setattr(agent, "BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setattr(agent, "API_KEY", "")
    assert agent.llm_ready() == (False, "chat_no_llm_key")
