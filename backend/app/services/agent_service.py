"""调用 Agent：加载历史消息、构造上下文、invoke、写回 assistant 消息，并提取推理步骤。"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from sqlmodel import Session
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

logger = logging.getLogger(__name__)

_MAX_LOG_STEP_CONTENT = 400

from app.services.session_service import (
    get_session_with_messages,
    add_message,
    ensure_session_title_from_first_message,
)
from app.agent.factory import get_agent
from app.schemas.session import InferenceStep
from config import settings


def _messages_to_langchain(db_messages: list) -> list[BaseMessage]:
    """
    将 DB 消息转为 LangChain 消息。DeepSeek-Reasoner 多轮/工具调用时，
    历史中的 assistant 消息必须带 reasoning_content；DeepSeek-chat 不需要。
    见：
    https://api-docs.deepseek.com/guides/thinking_mode#tool-calls
    """
    model_key = (settings.default_model or "").strip().lower()
    is_reasoner = "deepseek-reasoner" in model_key or model_key.endswith("reasoner")
    out = []
    for m in db_messages:
        role = getattr(m, "role", None) or (m.role if hasattr(m, "role") else "user")
        content = getattr(m, "content", None) or (m.content if hasattr(m, "content") else "")
        if role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            if is_reasoner:
                meta = getattr(m, "metadata_", None) or {}
                reasoning = (meta.get("reasoning_content") or "") if isinstance(meta, dict) else ""
                out.append(AIMessage(content=content, additional_kwargs={"reasoning_content": reasoning}))
            else:
                out.append(AIMessage(content=content))
    return out


def _ai_message_final_content(msg: Any) -> str:
    """
    DeepSeek-Reasoner 等推理模型：AIMessage 的 content 为最终回答，
    additional_kwargs.reasoning_content 为思考过程。只返回用于展示/入库的最终回答。
    """
    content = getattr(msg, "content", None)
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return str(content)


def _is_tool_message(msg: Any) -> bool:
    """判断消息是否为 ToolMessage（工具返回）。"""
    msg_type = getattr(msg, "type", "") or getattr(msg, "__class__", type(msg)).__name__
    return msg_type == "tool" or "ToolMessage" in str(type(msg).__name__)


def _ai_message_reasoning_content(msg: Any) -> str:
    """从 AIMessage 取出 reasoning_content（DeepSeek-Reasoner 的思考过程）。"""
    kwargs = getattr(msg, "additional_kwargs", None) or {}
    r = kwargs.get("reasoning_content") if isinstance(kwargs, dict) else None
    if r and isinstance(r, str) and r.strip():
        return r
    return ""


def _message_to_inference_steps(msg: Any) -> list[InferenceStep]:
    """从单条 message 中提取推理步骤（用于流式推送）。"""
    steps: list[InferenceStep] = []
    msg_type = getattr(msg, "type", "") or getattr(msg, "__class__", type(msg)).__name__
    if msg_type == "ai" or "AIMessage" in str(type(msg).__name__):
        reasoning = _ai_message_reasoning_content(msg)
        tool_calls = getattr(msg, "tool_calls", None) or []
        content = _ai_message_final_content(msg)
        if reasoning:
            steps.append(InferenceStep(kind="thinking", content=reasoning[:_MAX_LOG_STEP_CONTENT * 2]))
        if content and (reasoning or tool_calls):
            steps.append(InferenceStep(kind="thinking", content=content[:_MAX_LOG_STEP_CONTENT * 2]))
        for tc in tool_calls:
            name = tc.get("name", "tool") if isinstance(tc, dict) else getattr(tc, "name", "tool")
            args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
            steps.append(InferenceStep(kind="tool_call", name=name, content=str(args)[:300]))
    if _is_tool_message(msg):
        name = getattr(msg, "name", "tool")
        content = getattr(msg, "content", None) or ""
        steps.append(InferenceStep(kind="tool_result", name=name, content=str(content)[:500]))
    return steps


def _extract_inference_steps(result_messages: list[Any]) -> list[InferenceStep]:
    """从 Agent 返回的 messages 中提取思考、工具调用与结果，供推理框展示。"""
    steps: list[InferenceStep] = []
    for msg in result_messages:
        msg_type = getattr(msg, "type", "") or getattr(msg, "__class__", type(msg)).__name__
        if msg_type == "ai" or "AIMessage" in str(type(msg).__name__):
            reasoning = _ai_message_reasoning_content(msg)
            if reasoning:
                steps.append(InferenceStep(kind="thinking", content=reasoning[:_MAX_LOG_STEP_CONTENT * 2]))
            content = getattr(msg, "content", None)
            if content and isinstance(content, str) and content.strip() and not reasoning:
                steps.append(InferenceStep(kind="thinking", content=content[:500]))
            tool_calls = getattr(msg, "tool_calls", None) or []
            for tc in tool_calls:
                name = tc.get("name", "tool") if isinstance(tc, dict) else getattr(tc, "name", "tool")
                args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                steps.append(
                    InferenceStep(kind="tool_call", name=name, content=str(args)[:300])
                )
        if _is_tool_message(msg):
            name = getattr(msg, "name", "tool")
            content = getattr(msg, "content", None) or ""
            steps.append(
                InferenceStep(kind="tool_result", name=name, content=str(content)[:500])
            )
    return steps


def _log_execute_results(session_id: int, result_messages: list[Any]) -> None:
    """记录 execute 工具的执行日志（成功/失败均输出），便于排查 stdout 未捕获等问题。"""
    for msg in result_messages:
        if not _is_tool_message(msg):
            continue
        if getattr(msg, "name", "") != "execute":
            continue
        content_str = str(getattr(msg, "content", None) or "").strip()
        succeeded = "exit code: 0" in content_str.lower() or "succeeded" in content_str.lower()
        status = "成功" if succeeded else "失败/异常"
        preview = (content_str[:800] + "\n...(截断)") if len(content_str) > 800 else (content_str or "<无输出>")
        logger.info("execute 工具执行%s | session_id=%s | output_len=%d\n---\n%s\n---", status, session_id, len(content_str), preview)


def _format_inference_steps_for_log(steps: list[InferenceStep]) -> str:
    """将推理步骤格式化为可读日志（截断内容，避免过长）。"""
    lines: list[str] = []
    for i, s in enumerate(steps, start=1):
        name = f" name={s.name}" if s.name else ""
        content = (s.content or "").replace("\r\n", "\n").replace("\r", "\n")
        content = content[:_MAX_LOG_STEP_CONTENT]
        lines.append(f"{i:02d}. kind={s.kind}{name} content={content!r}")
    return "\n".join(lines)


def _thread_id(session_id: int) -> str:
    """
    DeepAgents/LangGraph 使用 thread_id 做对话状态（checkpointer）隔离。
    当切换到 deepseek-reasoner 时，旧线程状态里可能存在不含 reasoning_content 的 assistant 消息，
    会导致 DeepSeek 400（Missing reasoning_content）。这里按模型隔离 thread_id，避免状态污染。
    """
    model_key = (settings.default_model or "").strip().lower()
    return f"{session_id}:{model_key}"


def chat(db: Session, session_id: int, user_message: str) -> tuple[str, int, datetime, list[InferenceStep]]:
    """
    在指定会话中发送用户消息，调用 Agent 得到回复并写入 DB。
    已适配 DeepSeek-Reasoner：历史 assistant 带 reasoning_content（由 _messages_to_langchain 注入），
    本轮回复将 content 与 reasoning_content 分别入库，供下一轮请求符合 API 要求。
    返回 (assistant_content, message_id, created_at, inference_steps)。
    """
    logger.info(
        "agent.invoke start | session_id=%s | user_message_len=%s",
        session_id,
        len(user_message),
    )
    _, db_messages = get_session_with_messages(db, session_id)
    history = _messages_to_langchain(db_messages)
    add_message(db, session_id, "user", user_message)
    ensure_session_title_from_first_message(db, session_id, user_message)

    agent = get_agent()
    config = {"configurable": {"thread_id": _thread_id(session_id)}}
    messages_for_agent = history + [HumanMessage(content=user_message)]
    t0 = time.perf_counter()
    try:
        logger.info(
            "agent.invoke | session_id=%s | messages_for_agent=%s",
            session_id,
            messages_for_agent,
        )
        result = agent.invoke({"messages": messages_for_agent}, config=config)
    except Exception as e:
        logger.exception("agent.invoke failed | session_id=%s | error=%s", session_id, e)
        raise
    elapsed = time.perf_counter() - t0
    result_messages = result.get("messages", [])
    logger.debug(
        "agent.invoke result | session_id=%s | result_messages=%s ",
        session_id,
        len(result_messages),
    )
    _log_execute_results(session_id, result_messages)
    inference_steps = _extract_inference_steps(result_messages)
    tool_call_count = sum(1 for s in inference_steps if s.kind == "tool_call")

    # DeepSeek-Reasoner：最后一条 AI 消息的 content=最终回答，additional_kwargs.reasoning_content=思考过程
    last_ai_msg = None
    for msg in reversed(result_messages):
        if getattr(msg, "type", "") == "ai":
            last_ai_msg = msg
            break
    assistant_content = _ai_message_final_content(last_ai_msg) if last_ai_msg else ""
    reasoning = _ai_message_reasoning_content(last_ai_msg) if last_ai_msg else ""
    model_key = (settings.default_model or "").strip().lower()
    is_reasoner = "deepseek-reasoner" in model_key or model_key.endswith("reasoner")
    meta = {"reasoning_content": reasoning} if is_reasoner else None
    m = add_message(db, session_id, "assistant", assistant_content, metadata=meta)
    logger.info(
        "agent.invoke done | session_id=%s | duration_sec=%.2f | result_messages=%s | inference_steps=%s | tool_calls=%s | assistant_len=%s",
        session_id,
        elapsed,
        len(result_messages),
        len(inference_steps),
        tool_call_count,
        len(assistant_content),
    )
    if logger.isEnabledFor(logging.DEBUG) and inference_steps:
        logger.debug(
            "inference_steps | session_id=%s\n%s",
            session_id,
            _format_inference_steps_for_log(inference_steps),
        )
    return assistant_content, m.id, m.created_at, inference_steps


def _sse_event(payload: dict[str, Any]) -> str:
    """格式化为 SSE 文本事件。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def chat_stream(
    db: Session,
    session_id: int,
    user_message: str,
) -> Iterator[str]:
    """
    流式对话接口：
    - 使用 deepagents 的 agent.stream 获取增量 messages；
    - 按 delta 形式将 assistant 内容流式推送给前端；
    - 结束后写入 DB，并附带推理步骤的最终事件。
    """
    logger.info(
        "agent.stream start | session_id=%s | user_message=%s",
        session_id,
        user_message,
    )
    _, db_messages = get_session_with_messages(db, session_id)
    history = _messages_to_langchain(db_messages)
    add_message(db, session_id, "user", user_message)
    ensure_session_title_from_first_message(db, session_id, user_message)

    agent = get_agent()
    config = {"configurable": {"thread_id": _thread_id(session_id)}}
    messages_for_agent = history + [HumanMessage(content=user_message)]

    # 提前给前端一个开始事件，方便显示“正在思考…”
    yield _sse_event({"event": "start"})

    t0 = time.perf_counter()
    assistant_content = ""
    last_messages: list[Any] = []

    try:
        logger.info(
            "agent.stream | session_id=%s | messages_for_agent=%s",
            session_id,
            messages_for_agent,
        )
        seen_step_keys: set[tuple[str, str | None, str]] = set()
        last_msg_was_tool = False
        for event in agent.stream(
            {"messages": messages_for_agent},
            config=config,
            stream_mode="messages",
            subgraphs=True,
        ):
            # v1: (namespace, (msg, metadata))；无 subgraphs 时可能为 (msg, metadata)
            logger.info("agent.stream event | session_id=%s | event=%s", session_id, event)
            if isinstance(event, (list, tuple)):
                if len(event) == 2 and hasattr(event[0], "content"):
                    msg, _metadata = event[0], event[1]
                elif len(event) >= 2 and isinstance(event[1], (list, tuple)) and len(event[1]) >= 2:
                    msg, _metadata = event[1][0], event[1][1]
                else:
                    continue
            else:
                continue
            is_tool_msg = _is_tool_message(msg)
            # logger.info(f"消息内容:{msg},是否为工具消息:{is_tool_msg}")
            # 1. 流式推送推理步骤（思考、工具调用、工具结果）
            for step in _message_to_inference_steps(msg):
                key = (step.kind, step.name, (step.content or "")[:80])
                if key not in seen_step_keys:
                    seen_step_keys.add(key)
                    yield _sse_event({"event": "inference_step", "step": step.model_dump()})

            # 2. 流式推送最终答案：有 content 且无 reasoning/tool_calls 时统一发 chunk
            # - 有 reasoning/tool_calls 的 content 已在 1 中作为 inference_step 推送
            # - tool_content=true 表示紧接工具返回的内容（多为回显），前端可在 tool_content true->false 时清空
            # - tool_content=false 表示大模型最终结果
            new_content = _ai_message_final_content(msg)
            has_reasoning = bool(_ai_message_reasoning_content(msg))
            has_tool_calls = bool(getattr(msg, "tool_calls", None))
            if new_content and not has_reasoning and not has_tool_calls:
                if new_content.startswith(assistant_content):
                    delta = new_content[len(assistant_content) :]
                else:
                    delta = new_content
                assistant_content = new_content
                if delta:
                    yield _sse_event(
                        {
                            "event": "chunk",
                            "delta": delta,
                            "content": assistant_content,
                            "tool_content": is_tool_msg,
                        }
                    )

            last_msg_was_tool = is_tool_msg

        # 流结束后获取最终状态，用于 inference_steps
        try:
            state = agent.get_state(config)
            if state and hasattr(state, "values"):
                vals = state.values
            else:
                vals = state if isinstance(state, dict) else {}
            if isinstance(vals, dict):
                last_messages = vals.get("messages") or []
        except Exception:
            last_messages = []
    except Exception as e:
        logger.exception("agent.stream failed | session_id=%s | error=%s", session_id, e)
        yield _sse_event({"event": "error", "message": str(e)})
        return

    elapsed = time.perf_counter() - t0
    result_messages = last_messages
    _log_execute_results(session_id, result_messages)
    inference_steps = _extract_inference_steps(result_messages)
    tool_call_count = sum(1 for s in inference_steps if s.kind == "tool_call")

    last_ai_msg = None
    for msg in reversed(result_messages):
        if getattr(msg, "type", "") == "ai":
            last_ai_msg = msg
            break
    reasoning = _ai_message_reasoning_content(last_ai_msg) if last_ai_msg else ""
    model_key = (settings.default_model or "").strip().lower()
    is_reasoner = "deepseek-reasoner" in model_key or model_key.endswith("reasoner")
    meta = {"reasoning_content": reasoning} if is_reasoner else None
    m = add_message(db, session_id, "assistant", assistant_content, metadata=meta)

    logger.info(
        "agent.stream done | session_id=%s | duration_sec=%.2f | result_messages=%s | inference_steps=%s | tool_calls=%s | assistant_len=%s",
        session_id,
        elapsed,
        len(result_messages),
        len(inference_steps),
        tool_call_count,
        len(assistant_content),
    )
    if logger.isEnabledFor(logging.DEBUG) and inference_steps:
        logger.debug(
            "inference_steps | session_id=%s\n%s",
            session_id,
            _format_inference_steps_for_log(inference_steps),
        )

    # 最后一条完成事件，携带元数据 & 推理过程
    yield _sse_event(
        {
            "event": "end",
            "content": assistant_content,
            "message_id": m.id,
            "created_at": m.created_at.isoformat(),
            "inference_steps": [s.model_dump() for s in inference_steps],
        }
    )


def _augment_message_with_files(user_message: str, files_info: list[dict[str, Any]]) -> str:
    """将文件名与物理路径注入 user_message，供 chat_with_files / chat_stream_with_files 复用。"""
    if not files_info:
        return user_message
    backend_root = Path(__file__).resolve().parent.parent.parent
    uploads_root = backend_root / "data" / "uploads"
    entries: list[str] = []
    for info in files_info:
        name = info.get("name")
        path = info.get("path")
        if not name or not path:
            continue
        normalized = path.replace("\\", "/")
        if "uploads/" in normalized:
            suffix = normalized.split("uploads/", 1)[-1]
        else:
            suffix = normalized
        abs_path = str((uploads_root / suffix).resolve())
        entries.append(f"{name} -> {abs_path}")
    files_text = "\n".join(entries)
    extra_hint = (
        "\n\n[已上传文件列表]\n"
        f"{files_text}\n"
        "路径说明：读纯文本用 read_file + 上述绝对路径；其他文件（PDF、Word 等）优先使用技能；execute 执行时用绝对路径。不要使用虚拟路径。\n"
    )
    return f"{user_message}{extra_hint}"


def chat_with_files(
    db: Session,
    session_id: int,
    user_message: str,
    files_info: list[dict[str, Any]],
) -> tuple[str, int, datetime, list[InferenceStep]]:
    """
    带文件信息的对话入口（非流式）：
    - 将「文件名 + 物理路径」显式注入到本轮 user_message 中；
    - 复用 chat。
    """
    augmented = _augment_message_with_files(user_message, files_info)
    return chat(db, session_id, augmented)


def chat_stream_with_files(
    db: Session,
    session_id: int,
    user_message: str,
    files_info: list[dict[str, Any]],
) -> Iterator[str]:
    """
    带文件信息的流式对话：注入文件路径后，复用 chat_stream 进行流式输出。
    """
    augmented = _augment_message_with_files(user_message, files_info)
    yield from chat_stream(db, session_id, augmented)
