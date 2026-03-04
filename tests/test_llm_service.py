import json
from unittest.mock import patch, MagicMock


def _make_response(content="Hello", tool_calls=None, prompt_tokens=10, completion_tokens=5):
    """Build a mock OpenAI chat completion response."""
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls

    choice = MagicMock()
    choice.message = message

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _make_tool_call(call_id="call_1", name="query_data", arguments=None):
    """Build a mock tool call object."""
    if arguments is None:
        arguments = {"query": "sales data"}
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments)
    return tc


@patch("api.services.llm.llm_service.execute_tool")
@patch("api.services.llm.llm_service.client")
def test_simple_reply(mock_client, mock_exec_tool):
    mock_client.chat.completions.create.return_value = _make_response("Hi there")

    from api.services.llm.llm_service import chat
    text, new_msgs, metadata = chat([{"role": "user", "content": "Hello"}])

    assert text == "Hi there"
    assert len(new_msgs) == 1
    assert new_msgs[0]["role"] == "assistant"
    assert len(metadata["llm_calls"]) == 1
    assert len(metadata["tool_executions"]) == 0
    mock_exec_tool.assert_not_called()


@patch("api.services.llm.llm_service.execute_tool")
@patch("api.services.llm.llm_service.client")
def test_tool_use_loop(mock_client, mock_exec_tool):
    tc = _make_tool_call()
    # First call: LLM wants to use a tool
    resp_with_tool = _make_response(content=None, tool_calls=[tc])
    # Second call: LLM gives final answer
    resp_final = _make_response(content="Sales are 1200")
    mock_client.chat.completions.create.side_effect = [resp_with_tool, resp_final]
    mock_exec_tool.return_value = ('{"results": []}', {"name": "query_data", "args": {}, "duration_ms": 10, "success": True})

    from api.services.llm.llm_service import chat
    text, new_msgs, metadata = chat([{"role": "user", "content": "Show sales"}])

    assert text == "Sales are 1200"
    # assistant(tool_call) + tool_result + assistant(final) = 3
    assert len(new_msgs) == 3
    assert metadata["llm_calls"].__len__() == 2
    assert metadata["tool_executions"].__len__() == 1
    mock_exec_tool.assert_called_once()


@patch("api.services.llm.llm_service.execute_tool")
@patch("api.services.llm.llm_service.client")
def test_max_rounds_exceeded(mock_client, mock_exec_tool):
    tc = _make_tool_call()
    # Every call returns a tool call, never a final answer
    mock_client.chat.completions.create.return_value = _make_response(content=None, tool_calls=[tc])
    mock_exec_tool.return_value = ('{"results": []}', {"name": "query_data", "args": {}, "duration_ms": 1, "success": True})

    from api.services.llm.llm_service import chat
    text, new_msgs, metadata = chat([{"role": "user", "content": "loop"}])

    assert "try again" in text.lower()
    assert mock_client.chat.completions.create.call_count == 5
