import json
import os
from typing import Any

import httpx
from openai import OpenAI


OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

GUARDRAIL_URL = os.getenv(
    "GUARDRAIL_URL",
    "http://localhost:8000",
)

GUARDRAIL_API_KEY = os.environ.get(
    "GUARDRAIL_API_KEY",
)

MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "nvidia/nemotron-3.5-lightning:free",
)


client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    default_headers={
        "HTTP-Referer": "https://github.com/harish040120/action-guardrail",
        "X-Title": "Action Guardrail",
    },
)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "db_delete",
            "description": (
                "Delete records from a database table. "
                "This is a potentially destructive operation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Database table name",
                    },
                    "record_count": {
                        "type": "integer",
                        "description": "Number of records to delete",
                    },
                },
                "required": [
                    "table",
                    "record_count",
                ],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": (
                "Send an email to a recipient."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient_domain": {
                        "type": "string",
                        "description": (
                            "Domain of the email recipient"
                        ),
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject",
                    },
                },
                "required": [
                    "recipient_domain",
                ],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the contents of a file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path of the file to read",
                    },
                },
                "required": [
                    "path",
                ],
                "additionalProperties": False,
            },
        },
    },
]


def call_guardrail(
    tool_name: str,
    arguments: dict[str, Any],
    agent_id: str = "openrouter-agent",
) -> dict[str, Any]:

    if not GUARDRAIL_API_KEY:
        raise RuntimeError(
            "GUARDRAIL_API_KEY is not configured"
        )

    response = httpx.post(
        f"{GUARDRAIL_URL}/v1/actions/execute",
        headers={
            "Content-Type": "application/json",
            "x-api-key": GUARDRAIL_API_KEY,
        },
        json={
            "tool_name": tool_name,
            "arguments": arguments,
            "agent_id": agent_id,
        },
        timeout=30.0,
    )

    try:
        data = response.json()
    except Exception:
        data = {
            "detail": response.text
        }

    return {
        "status_code": response.status_code,
        "data": data,
    }


def run_agent(
    user_message: str,
    agent_id: str = "openrouter-agent",
) -> dict[str, Any]:

    messages = [
        {
            "role": "system",
            "content": (
                "You are an autonomous AI agent with access to tools.\n\n"
                "When the user explicitly asks you to perform an action "
                "that matches an available tool, you should call that tool "
                "instead of merely describing what you would do.\n\n"
                "Examples:\n"
                "If the user says 'delete 500 users', call db_delete "
                "with table='users' and record_count=500.\n"
                "If the user says 'delete 5 sessions', call db_delete "
                "with table='sessions' and record_count=5.\n"
                "If the user asks to send an email to gmail.com, call "
                "send_email with recipient_domain='gmail.com'.\n"
                "If the user asks to read a file, call read_file with "
                "the requested path.\n\n"
                "Do not decide whether an action is safe or permitted. "
                "The Action Guardrail makes that decision.\n\n"
                "Your responsibility is to propose the appropriate tool "
                "call. Every tool call must pass through the Action "
                "Guardrail before execution."
            ),
        },
        {
            "role": "user",
            "content": user_message,
        },
    ]

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
    )

    message = response.choices[0].message

    # No tool call — ordinary LLM response
    if not message.tool_calls:

        return {
            "type": "final",
            "response": message.content,
        }

    results = []

    for tool_call in message.tool_calls:

        tool_name = tool_call.function.name

        try:
            arguments = json.loads(
                tool_call.function.arguments
            )
        except json.JSONDecodeError:

            results.append({
                "tool_name": tool_name,
                "verdict": "invalid_tool_arguments",
                "error": tool_call.function.arguments,
            })

            continue

        print("\n========================================")
        print("LLM PROPOSED TOOL CALL")
        print("========================================")
        print(f"Tool:      {tool_name}")
        print(
            f"Arguments: {json.dumps(arguments, indent=2)}"
        )

        # IMPORTANT:
        # The LLM does NOT execute the tool.
        # The request goes through the Action Guardrail.
        guardrail_result = call_guardrail(
            tool_name=tool_name,
            arguments=arguments,
            agent_id=agent_id,
        )

        status_code = guardrail_result["status_code"]
        data = guardrail_result["data"]

        print("\n========================================")
        print("ACTION GUARDRAIL")
        print("========================================")
        print(f"HTTP status: {status_code}")
        print(
            f"Response: {json.dumps(data, indent=2)}"
        )

        results.append({
            "tool_name": tool_name,
            "arguments": arguments,
            "guardrail": data,
            "status_code": status_code,
        })

    return {
        "type": "tool_calls",
        "results": results,
    }


if __name__ == "__main__":

    import sys

    if len(sys.argv) < 2:
        print(
            'Usage: python agent/openrouter_agent.py',
            '"your request"'
        )
        raise SystemExit(1)

    prompt = " ".join(sys.argv[1:])

    result = run_agent(prompt)

    print("\n========================================")
    print("FINAL RESULT")
    print("========================================")

    print(
        json.dumps(
            result,
            indent=2,
            default=str,
        )
    )
