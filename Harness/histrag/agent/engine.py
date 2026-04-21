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
    content: Any  # str or list of content blocks (text, tool_use, tool_result)


@dataclass
class ToolUseBlock:
    """A tool use in a message."""
    name: str
    input: dict[str, Any]
    tool_call_id: str = ""


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
        print(f"prompt:{prompt}")
        self._messages.append(ConversationMessage(role="user", content=prompt))
        api_messages = self._build_api_messages()
        tools = self.tool_registry.to_api_schema()
        # print(f"[DEBUG] rag_query tool schema: {[t for t in tools if t['name'] == 'rag_query']}", flush=True)

        turn = 0
        while turn < self.max_turns:
            print(f"=============no.{turn + 1} agent_loop:================")
            turn += 1

            full_response = ""
            tool_calls: list[ToolUseBlock] = []

            try:
                from ..api import ApiMessageRequest
                request = ApiMessageRequest(
                    model=self.model,
                    messages=api_messages,
                    system_prompt=f"{self.system_prompt}\n\n【当前用户问题】: {prompt}\n\n调用 rag_query 时必须将上述用户问题填入 query 参数。",
                    tools=tools,
                )
                # print(f"[DEBUG] system_prompt length: {len(self.system_prompt) if self.system_prompt else 0}", flush=True)
                # print(f"[DEBUG] system_prompt first 200: {self.system_prompt[:200] if self.system_prompt else 'EMPTY'}", flush=True)

                async for event in self.api_client.stream_message(request):
                    #print(f"event:{event}")
                    if hasattr(event, "text"):
                        full_response += event.text
                        yield AssistantTextDelta(text=event.text)
                    elif hasattr(event, "name") and hasattr(event, "input"):
                        # ApiToolUseEvent
                        tool_calls.append(ToolUseBlock(name=event.name, input=event.input, tool_call_id=event.tool_call_id))
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

                    context = ToolExecutionContext(
                        cwd=self.cwd,
                        metadata={"original_question": prompt},
                    )
                    try:
                        result: ToolResult = await tool.execute(parsed, context)
                        yield ToolExecutionCompleted(
                            tool_name=tc.name,
                            result=result.output,
                            is_error=result.is_error,
                        )
                        # If tool returned error, store as plain text to avoid tool_call_id mismatch with MiniMax API
                        if result.is_error:
                            self._messages.append(ConversationMessage(
                                role="user",
                                content=f"[工具错误] {result.output}",
                            ))
                        else:
                            # Store assistant message with tool_use (required for MiniMax to track tool calls)
                            self._messages.append(ConversationMessage(
                                role="assistant",
                                content=[
                                    {
                                        "type": "tool_use",
                                        "id": tc.tool_call_id,
                                        "name": tc.name,
                                        "input": tc.input,
                                    }
                                ],
                            ))
                            # Store user message with tool_result
                            self._messages.append(ConversationMessage(
                                role="user",
                                content=[
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": tc.tool_call_id,
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
                            content=f"[工具执行错误] {e}",
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
                # msg.content is a list of content blocks (text, tool_use, tool_result)
                api_content = []
                for item in msg.content:
                    if isinstance(item, dict):
                        if item.get("type") == "tool_result":
                            # Use tool_use_id (not tool_call_id) - matches how we stored it
                            tool_id = item.get("tool_use_id", "")
                            print(f"[DEBUG] tool_result tool_use_id: {tool_id}", flush=True)
                            api_content.append({
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "content": item["content"],
                            })
                        elif item.get("type") == "tool_use":
                            # MiniMax API needs tool_use id to be preserved
                            api_content.append({
                                "type": "tool_use",
                                "id": item.get("id", ""),
                                "name": item.get("name", ""),
                                "input": item.get("input", {}),
                            })
                    elif hasattr(item, "type"):
                        if item.type == "tool_result":
                            tool_id = getattr(item, "tool_use_id", "")
                            content = getattr(item, "content", str(item))
                            if isinstance(content, str):
                                api_content.append({
                                    "type": "tool_result",
                                    "tool_use_id": tool_id,
                                    "content": content,
                                })
                        elif item.type == "tool_use":
                            api_content.append({
                                "type": "tool_use",
                                "id": getattr(item, "id", ""),
                                "name": getattr(item, "name", ""),
                                "input": getattr(item, "input", {}),
                            })
                if api_content:
                    messages.append({"role": msg.role, "content": api_content})
        print(f"[DEBUG] _build_api_messages: {messages}", flush=True)
        return messages


__all__ = ["AgentEngine", "ConversationMessage", "ToolUseBlock"]