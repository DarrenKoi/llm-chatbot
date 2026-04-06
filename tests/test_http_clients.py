import json
import logging

import httpx
import pytest
from api.cube.client import CubeClientError, _send_cube_request, send_multimessage, send_richnotification
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
        "api.llm.service.get_system_prompt",
        lambda user_profile_text="": f"system prompt with korean time::{user_profile_text}",
    )
    post_mock = mocker.patch(
        "api.llm.service.httpx.post",
        return_value=_response(json_body={"choices": [{"message": {"content": "hello"}}]}),
    )

    reply = generate_reply(history=[], user_message="hi", user_profile_text="- 이름: 홍길동")

    assert reply == "hello"
    post_mock.assert_called_once_with(
        "https://llm.example.com/v1/chat/completions",
        json={
            "model": "gpt-test",
            "messages": [
                {
                    "role": "system",
                    "content": "system prompt with korean time::- 이름: 홍길동",
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


def test_send_multimessage_emits_info_logs(mocker, monkeypatch, caplog):
    monkeypatch.setattr("api.config.CUBE_MULTIMESSAGE_URL", "https://cube.example.com/api/multiMessage")
    monkeypatch.setattr("api.config.CUBE_API_ID", "bot-id")
    monkeypatch.setattr("api.config.CUBE_API_TOKEN", "bot-token")
    mocker.patch(
        "api.cube.client.httpx.post",
        return_value=_response(text="accepted"),
    )

    caplog.set_level(logging.INFO, logger="api.cube.client")

    result = send_multimessage(user_id="u1", reply_message="hello")

    assert result == {"raw": "accepted"}
    assert "Cube multiMessage request started" in caplog.text
    assert "Cube multiMessage request completed" in caplog.text


def test_send_richnotification_emits_info_logs(mocker, monkeypatch, caplog):
    monkeypatch.setattr("api.config.CUBE_RICHNOTIFICATION_URL", "https://cube.example.com/legacy/richnotification")
    monkeypatch.setattr("api.config.CUBE_BOT_ID", "bot-id")
    monkeypatch.setattr("api.config.CUBE_BOT_TOKEN", "bot-token")
    mocker.patch(
        "api.cube.client.httpx.post",
        return_value=_response(text="accepted"),
    )

    caplog.set_level(logging.INFO, logger="api.cube.client")

    result = send_richnotification(user_id="u1", channel_id="c1", reply_message="hello")

    assert result == {"raw": "accepted"}
    assert "Cube richnotification request started" in caplog.text
    assert "Cube richnotification request completed" in caplog.text
