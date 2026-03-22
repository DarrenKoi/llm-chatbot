import json

import httpx
import pytest
from api.cube.client import CubeClientError, _send_cube_request
from api.llm.service import LLMServiceError, generate_reply


def _response(
    *,
    status_code: int = 200,
    url: str = "https://example.test/api",
    json_body: object | None = None,
    text: str = "",
) -> httpx.Response:
    if json_body is not None:
        return httpx.Response(status_code, json=json_body, request=httpx.Request("POST", url))
    return httpx.Response(status_code, text=text, request=httpx.Request("POST", url))


def test_generate_reply_uses_httpx_post(mocker, monkeypatch):
    monkeypatch.setattr("api.config.LLM_BASE_URL", "https://llm.example.com/v1")
    monkeypatch.setattr("api.config.LLM_MODEL", "gpt-test")
    monkeypatch.setattr("api.config.LLM_API_KEY", "secret")
    monkeypatch.setattr(
        "api.config.LLM_SYSTEM_PROMPT_OVERRIDE",
        "You are ITC OSS (Infra. Tech Center / One Stop Solution) Agent, Answer kindly in Korean.",
    )
    post_mock = mocker.patch(
        "api.llm.service.httpx.post",
        return_value=_response(json_body={"choices": [{"message": {"content": "hello"}}]}),
    )

    reply = generate_reply(history=[], user_message="hi")

    assert reply == "hello"
    post_mock.assert_called_once_with(
        "https://llm.example.com/v1/chat/completions",
        json={
            "model": "gpt-test",
            "messages": [
                {
                    "role": "system",
                    "content": "You are ITC OSS (Infra. Tech Center / One Stop Solution) Agent, Answer kindly in Korean.",
                },
                {"role": "user", "content": "hi"},
            ],
        },
        headers={"Authorization": "Bearer secret"},
        timeout=30,
    )


def test_generate_reply_raises_for_http_status(mocker, monkeypatch):
    monkeypatch.setattr("api.config.LLM_BASE_URL", "https://llm.example.com/v1")
    monkeypatch.setattr("api.config.LLM_MODEL", "gpt-test")
    mocker.patch(
        "api.llm.service.httpx.post",
        return_value=_response(status_code=502, text="upstream failed"),
    )

    with pytest.raises(LLMServiceError, match="LLM request failed with HTTP 502: upstream failed"):
        generate_reply(history=[], user_message="hi")


def test_generate_reply_raises_for_request_error(mocker, monkeypatch):
    monkeypatch.setattr("api.config.LLM_BASE_URL", "https://llm.example.com/v1")
    monkeypatch.setattr("api.config.LLM_MODEL", "gpt-test")
    mocker.patch(
        "api.llm.service.httpx.post",
        side_effect=httpx.ConnectError(
            "connection refused",
            request=httpx.Request("POST", "https://llm.example.com/v1/chat/completions"),
        ),
    )

    with pytest.raises(LLMServiceError, match="LLM request failed: connection refused"):
        generate_reply(history=[], user_message="hi")


def test_send_cube_request_returns_raw_text_for_non_json_body(mocker):
    mocker.patch(
        "api.cube.client.httpx.post",
        return_value=_response(text="accepted"),
    )

    result = _send_cube_request(
        url="https://cube.example.com/api/multiMessage",
        payload={"hello": "world"},
        label="multiMessage",
    )

    assert result == {"raw": "accepted"}


def test_send_cube_request_wraps_non_object_json_payload(mocker):
    mocker.patch(
        "api.cube.client.httpx.post",
        return_value=httpx.Response(
            200,
            content=json.dumps(["ok"]).encode("utf-8"),
            request=httpx.Request("POST", "https://cube.example.com/api/multiMessage"),
            headers={"Content-Type": "application/json"},
        ),
    )

    result = _send_cube_request(
        url="https://cube.example.com/api/multiMessage",
        payload={"hello": "world"},
        label="multiMessage",
    )

    assert result == {"payload": ["ok"]}


def test_send_cube_request_raises_for_http_status(mocker):
    mocker.patch(
        "api.cube.client.httpx.post",
        return_value=_response(status_code=503, text="temporarily unavailable"),
    )

    with pytest.raises(CubeClientError, match="Cube richnotification failed with HTTP 503: temporarily unavailable"):
        _send_cube_request(
            url="https://cube.example.com/legacy/richnotification",
            payload={"hello": "world"},
            label="richnotification",
        )
