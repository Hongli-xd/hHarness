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
                    # ── 自动注入 linked_view ──────────────────────────────
                    # 每次模型写完最终答案后，自动调用 linked_view 工具
                    # 从答案文本中提取时间事件和地名，生成联动地图+时间轴页面
                    linked_view_tool = self.tool_registry.get("linked_view")
                    if linked_view_tool and full_response:
                        async for lv_event in self._auto_invoke_linked_view(
                            full_response, prompt, linked_view_tool
                        ):
                            yield lv_event
                    # ─────────────────────────────────────────────────────
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
                        # Fallback: if query is None, use prompt (defensive guard)
                        if tc.input.get("query") is None:
                            tc.input["query"] = prompt
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
    async def _auto_invoke_linked_view(
        self,
        answer_text: str,
        original_prompt: str,
        linked_view_tool: Any,
    ):
        """答案写完后，自动用 LLM 提取事件+地名，调用 linked_view 工具。
 
        调用逻辑：
        1. 构造专用提取 prompt（原始问题 + 完整答案）
        2. 用独立的单轮 API 请求（不污染主对话历史）
        3. 模型只能调用 linked_view，返回结构化数据
        4. 引擎直接执行工具，yield 事件通知 CLI/前端
        """
        from ..api import ApiMessageRequest
 
        extraction_prompt = (
            f"以下是用户的历史研究问题和已生成的回答。\n\n"
            f"【用户问题】\n{original_prompt}\n\n"
            f"【回答内容】\n{answer_text}\n\n"
            f"请调用 linked_view 工具，从上述回答中提取：\n"
            f"1. 所有明确提到年份的历史事件（events）\n"
            f"2. 所有出现的历史地名（places），提供准确经纬度\n"
            f"3. 每个事件的 place_names 填入该事件相关地名，"
            f"名称必须与 places 列表中的 name 完全一致\n"
            f"4. title 设为对问题的简短概括（10字以内）\n\n"
            f"经纬度使用现代坐标，精度到小数点后1位即可。"
        )
 
        tools = self.tool_registry.to_api_schema()
        lv_schema = [t for t in tools if t.get("name") == "linked_view"]
        if not lv_schema:
            return
 
        request = ApiMessageRequest(
            model=self.model,
            messages=[{"role": "user", "content": extraction_prompt}],
            system_prompt=(
                "你是结构化信息提取助手。"
                "请严格按工具 schema 提取信息并调用 linked_view 工具，不要输出任何其他文字。"
            ),
            tools=lv_schema,
        )
 
        tool_name = ""
        tool_input: dict = {}
 
        try:
            async for event in self.api_client.stream_message(request):
                if hasattr(event, "name") and hasattr(event, "input"):
                    tool_name = event.name
                    tool_input = event.input or {}
        except Exception as e:
            print(f"[linked_view extraction error] {e}", flush=True)
            return
 
        if tool_name != "linked_view":
            return
 
        yield ToolExecutionStarted(tool_name="linked_view", tool_input=tool_input)
 
        try:
            parsed = linked_view_tool.input_model.model_validate(tool_input)
        except Exception as e:
            yield ToolExecutionCompleted(
                tool_name="linked_view",
                result=f"linked_view input error: {e}",
                is_error=True,
            )
            return
 
        from ..agent import ToolExecutionContext
        context = ToolExecutionContext(
            cwd=self.cwd,
            metadata={"original_question": original_prompt},
        )
 
        try:
            result = await linked_view_tool.execute(parsed, context)
            yield ToolExecutionCompleted(
                tool_name="linked_view",
                result=result.output,
                is_error=result.is_error,
                metadata=getattr(result, "metadata", None),
            )
        except Exception as e:
            yield ToolExecutionCompleted(
                tool_name="linked_view",
                result=f"linked_view execution error: {e}",
                is_error=True,
            )
            
__all__ = ["AgentEngine", "ConversationMessage", "ToolUseBlock"]