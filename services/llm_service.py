import json

from openai import OpenAI

import config
from tools import TOOL_DEFINITIONS, execute_tool

client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)

MAX_TOOL_ROUNDS = 5


def chat(messages: list[dict]) -> tuple[str, list[dict]]:
    """Send messages to LLM with tool-use loop.

    Returns:
        (final_reply_text, new_messages) where new_messages contains all
        assistant/tool messages generated during this call.
    """
    new_messages = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=messages,
            tools=TOOL_DEFINITIONS,
        )
        choice = response.choices[0]
        assistant_msg = choice.message

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
        messages.append(msg_dict)
        new_messages.append(msg_dict)

        if not assistant_msg.tool_calls:
            return assistant_msg.content or "", new_messages

        for tool_call in assistant_msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            result = execute_tool(fn_name, fn_args)

            tool_msg = {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            }
            messages.append(tool_msg)
            new_messages.append(tool_msg)

    return "I encountered an issue processing your request. Please try again.", new_messages
