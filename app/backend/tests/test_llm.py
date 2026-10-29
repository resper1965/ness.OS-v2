import json

import httpx
import pytest

from app.integrations import gemini, llm, soc_agent
from app.ml import analyzer

_REAL = {"AsyncClient": httpx.AsyncClient, "Client": httpx.Client}
SCHEMA = {
    "type": "OBJECT",
    "properties": {"a": {"type": "STRING", "enum": ["x"]}, "n": {"type": "NUMBER"}},
    "required": ["a"],
}
REPLY = {
    "choices": [{"message": {"content": '{"a": "x"}'}}],
    "usage": {"prompt_tokens": 5, "completion_tokens": 2},
}


def _mock(monkeypatch, name, reply=REPLY):
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200, json=reply)

    monkeypatch.setattr(
        httpx,
        name,
        lambda **kw: _REAL[name](transport=httpx.MockTransport(handler), **kw),
    )
    return sent


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_api_key", "synthetic-key")


def test_request_body_and_parse(monkeypatch):
    sent = _mock(monkeypatch, "Client")
    text, usage = llm.chat_completion("sys", "usr", json_schema=SCHEMA)
    req = sent[0]
    body = json.loads(req.content)
    assert str(req.url) == "https://openrouter.ai/api/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer synthetic-key"
    assert req.headers["http-referer"] == "https://hub.ness.com.br"
    assert req.headers["x-title"] == "ness.OS"
    assert body["model"] == "google/gemini-2.5-flash"
    assert body["provider"] == {"data_collection": "deny", "require_parameters": True}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    js = body["response_format"]["json_schema"]
    assert body["response_format"]["type"] == "json_schema" and js["strict"] is True
    assert (
        js["schema"]["type"] == "object"
        and js["schema"]["additionalProperties"] is False
    )
    assert js["schema"]["properties"]["n"]["type"] == "number"
    assert js["schema"]["required"] == ["a", "n"]
    assert text == '{"a": "x"}' and usage == {
        "prompt_tokens": 5,
        "completion_tokens": 2,
    }


def test_no_schema_means_no_response_format(monkeypatch):
    sent = _mock(monkeypatch, "Client")
    llm.chat_completion("s", "u")
    assert "response_format" not in json.loads(sent[0].content)


@pytest.mark.asyncio
async def test_missing_key_makes_no_call(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_api_key", "")

    def forbidden(**kw):
        raise AssertionError("no HTTP without key")

    monkeypatch.setattr(httpx, "Client", forbidden)
    with pytest.raises(httpx.HTTPError):
        llm.chat_completion("s", "u")
    assert (await soc_agent.triage_wazuh_alert({"rule": {"id": "1"}}, "t"))[
        "action_taken"
    ]
    report = gemini.generate_postmortem({"fingerprint": "fp"}, [], [])
    assert "falhou" in report.summary


@pytest.mark.asyncio
async def test_async_variant(monkeypatch):
    _mock(monkeypatch, "AsyncClient")
    text, _ = await llm.achat_completion("s", "u", json_schema=SCHEMA)
    assert json.loads(text) == {"a": "x"}


@pytest.mark.asyncio
async def test_analyzer_uses_llm(monkeypatch):
    payload = {
        "executive_action_plan": "e",
        "technical_action_plan": "t",
        "urgency": "HIGH",
        "isolation_required": False,
        "probable_cause": "c",
        "recommended_playbook": "p",
    }
    _mock(
        monkeypatch,
        "AsyncClient",
        {"choices": [{"message": {"content": json.dumps(payload)}}]},
    )
    result = await analyzer.analyze_incident({"severity": 4})
    assert result.probable_cause == "c"


@pytest.mark.asyncio
async def test_soc_uses_llm(monkeypatch):
    triage = {
        "classification": "LOW",
        "confidence": 0.9,
        "summary": "s",
        "action_taken": "a",
    }
    _mock(
        monkeypatch,
        "AsyncClient",
        {"choices": [{"message": {"content": json.dumps(triage)}}]},
    )
    alert = {"rule": {"id": "1", "level": 3}}
    assert await soc_agent.triage_wazuh_alert(alert, "t") == triage


def test_postmortem_uses_llm(monkeypatch):
    monkeypatch.setattr(gemini.settings, "gemini_api_key", "")
    md = "## Resumo Executivo\nok\n"
    _mock(
        monkeypatch,
        "Client",
        {
            "choices": [{"message": {"content": md}}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 1},
        },
    )
    report = gemini.generate_postmortem({"fingerprint": "fp"}, [], [])
    assert report.summary == "ok" and report.prompt_tokens == 4
    assert report.gemini_model_used == "google/gemini-2.5-flash"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply",
    [
        {"choices": []},
        {"choices": [{"message": None}]},
        {"choices": [{"message": {"content": None}}]},
        {"error": {"message": "x"}},
    ],
)
async def test_unusable_body_falls_back(monkeypatch, reply):
    _mock(monkeypatch, "Client", reply)
    with pytest.raises(llm.LLMBadResponse):
        llm.chat_completion("s", "u")
    _mock(monkeypatch, "AsyncClient", reply)
    got = await soc_agent.triage_wazuh_alert({"rule": {"id": "1"}}, "t")
    assert got["confidence"] == 0.5
    _mock(monkeypatch, "Client", reply)
    assert "falhou" in gemini.generate_postmortem({"fingerprint": "f"}, [], []).summary


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        "{}",
        "[]",
        '{"classification":"BOGUS","confidence":0.9,"summary":"s","action_taken":"a"}',
        '{"classification":"LOW","confidence":NaN,"summary":"s","action_taken":"a"}',
        '{"classification":"LOW","confidence":Infinity,"summary":"s","action_taken":"a"}',
        '{"classification":"LOW","confidence":1.5,"summary":"s","action_taken":"a"}',
        '{"classification":"LOW","confidence":-0.1,"summary":"s","action_taken":"a"}',
        '{"classification":"LOW","confidence":true,"summary":"s","action_taken":"a"}',
        '{"classification":"LOW","confidence":"0.9","summary":"s","action_taken":"a"}',
        '{"classification":"LOW","confidence":0.9,"summary":"","action_taken":"a"}',
    ],
)
async def test_soc_invalid_reply_falls_back(monkeypatch, content):
    _mock(monkeypatch, "AsyncClient", {"choices": [{"message": {"content": content}}]})
    got = await soc_agent.triage_wazuh_alert({"rule": {"id": "1"}}, "t")
    assert got["classification"] == "HIGH" and got["confidence"] == 0.5
