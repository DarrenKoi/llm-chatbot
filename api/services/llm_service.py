import json
import time

from openai import OpenAI

from api import config
from api.tools import TOOL_DEFINITIONS, execute_tool

client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)

MAX_TOOL_ROUNDS = 5


def chat(messages: list[dict]) -> tuple[str, list[dict], dict]:
    """Send messages to LLM with tool-use loop.

    Returns:
        (final_reply_text, new_messages, metadata) where:
        - new_messages: all assistant/tool messages generated during this call
        - metadata: dict with llm_calls and tool_executions lists for logging
    """
    new_messages = []
    llm_calls = []
    tool_executions = []

    for _ in range(MAX_TOOL_ROUNDS):
        start = time.monotonic()
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=messages,
            tools=TOOL_DEFINITIONS,
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        choice = response.choices[0]
        assistant_msg = choice.message

        # Track per-call metrics
        call_info = {"duration_ms": duration_ms, "tool_calls": []}
        if response.usage:
            call_info["prompt_tokens"] = response.usage.prompt_tokens
            call_info["completion_tokens"] = response.usage.completion_tokens

        msg_dict = {"role": "assistant", "content": assistant_msg.content}
        if assistant_msg.tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in assistant_msg.tool_calls
            ]
            call_info["tool_calls"] = [tc.function.name for tc in assistant_msg.tool_calls]
        llm_calls.append(call_info)

        messages.append(msg_dict)
        new_messages.append(msg_dict)

        if not assistant_msg.tool_calls:
            metadata = {"llm_calls": llm_calls, "tool_executions": tool_executions}
            return assistant_msg.content or "", new_messages, metadata

        for tool_call in assistant_msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            result, exec_info = execute_tool(fn_name, fn_args)
            tool_executions.append(exec_info)

            tool_msg = {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            }
            messages.append(tool_msg)
            new_messages.append(tool_msg)

    metadata = {"llm_calls": llm_calls, "tool_executions": tool_executions}
    return "I encountered an issue processing your request. Please try again.", new_messages, metadata
