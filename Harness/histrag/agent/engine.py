"""Simple Agent Engine - minimal implementation replacing OpenHarness QueryEngine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

from .events import (
    AssistantTextDelta,
    AssistantTurnComplete,
    ToolExecutionStarted,
    ToolExecutionCompleted,
    ErrorEvent,
)
from .tools import ToolExecutionContext, ToolRegistry, ToolResult


@dataclass
class ConversationMessage:
    """A message with potential tool calls."""
    role: str
    content: Any  # str or list of tool calls


@dataclass
class ToolUseBlock:
    """A tool use in a message."""
    name: str
    input: dict[str, Any]


class AgentEngine:
    """Simple agent engine with tool calling capability."""

    def __init__(
        self,
        *,
        api_client: Any,
        tool_registry: ToolRegistry,
        system_prompt: str = "",
        model: str = "claude-sonnet-4-20250514",
        max_turns: int = 20,
        cwd: str | Path = ".",
    ):
        self.api_client = api_client
        self.tool_registry = tool_registry
        self.system_prompt = system_prompt
        self.model = model
        self.max_turns = max_turns
        self.cwd = Path(cwd)
        self._messages: list[ConversationMessage] = []

    def clear(self) -> None:
        """Clear conversation history."""
        self._messages = []

    def load_messages(self, messages: list[ConversationMessage]) -> None:
        """Load conversation history."""
        self._messages = messages

    async def submit_message(self, prompt: str) -> AsyncIterator[Any]:
        """Submit a message and run the agent loop."""
        self._messages.append(ConversationMessage(role="user", content=prompt))
        api_messages = self._build_api_messages()
        tools = self.tool_registry.to_api_schema()

        turn = 0
        while turn < self.max_turns:
            turn += 1

            full_response = ""
            tool_calls: list[ToolUseBlock] = []

            try:
                from ..api import ApiMessageRequest
                request = ApiMessageRequest(
                    model=self.model,
                    messages=api_messages,
                    system_prompt=self.system_prompt,
                    tools=tools,
                )

                async for event in self.api_client.stream_message(request):
                    if hasattr(event, "text"):
                        full_response += event.text
                        yield AssistantTextDelta(text=event.text)
                    elif hasattr(event, "name") and hasattr(event, "input"):
                        # ApiToolUseEvent
                        tool_calls.append(ToolUseBlock(name=event.name, input=event.input))
                    elif hasattr(event, "stop_reason"):
                        pass  # Terminal event

                if not tool_calls:
                    yield AssistantTurnComplete(content=full_response)
                    self._messages.append(ConversationMessage(role="assistant", content=full_response))
                    return

                for tc in tool_calls:
                    yield ToolExecutionStarted(tool_name=tc.name, tool_input=tc.input)

                    tool = self.tool_registry.get(tc.name)
                    if not tool:
                        yield ToolExecutionCompleted(
                            tool_name=tc.name,
                            result=f"Tool not found: {tc.name}",
                            is_error=True,
                        )
                        continue

                    try:
                        parsed = tool.input_model.model_validate(tc.input)
                    except Exception as e:
                        yield ToolExecutionCompleted(
                            tool_name=tc.name,
                            result=f"Invalid input: {e}",
                            is_error=True,
                        )
                        continue

                    context = ToolExecutionContext(cwd=self.cwd)
                    try:
                        result: ToolResult = await tool.execute(parsed, context)
                        yield ToolExecutionCompleted(
                            tool_name=tc.name,
                            result=result.output,
                            is_error=result.is_error,
                        )
                        self._messages.append(ConversationMessage(
                            role="user",
                            content=[
                                {
                                    "type": "tool_result",
                                    "name": tc.name,
                                    "content": result.output,
                                }
                            ],
                        ))
                    except Exception as e:
                        yield ToolExecutionCompleted(
                            tool_name=tc.name,
                            result=f"Execution error: {e}",
                            is_error=True,
                        )
                        self._messages.append(ConversationMessage(
                            role="user",
                            content=[
                                {
                                    "type": "tool_result",
                                    "name": tc.name,
                                    "content": f"Error: {e}",
                                }
                            ],
                        ))

                api_messages = self._build_api_messages()

            except Exception as e:
                yield ErrorEvent(error=str(e))
                return

        yield ErrorEvent(error=f"Max turns ({self.max_turns}) exceeded")

    def _build_api_messages(self) -> list[dict[str, Any]]:
        """Build messages for API call."""
        messages = []
        for msg in self._messages:
            if isinstance(msg.content, str):
                messages.append({"role": msg.role, "content": msg.content})
            else:
                for item in msg.content:
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        messages.append({
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "placeholder",
                                    "content": item["content"],
                                }
                            ],
                        })
        return messages


__all__ = ["AgentEngine", "ConversationMessage", "ToolUseBlock"]