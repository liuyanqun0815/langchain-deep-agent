"""将 DB 中的 Skill 转为 deepagents 可用的工具（Callable）。"""

import httpx
from typing import Any, Callable

from app.db.models import Skill


def _make_http_skill(name: str, description: str, config: dict[str, Any] | None) -> Callable[..., str]:
    """根据 config 生成 HTTP 请求类 skill。config 示例: {"url": "...", "method": "GET"}。"""

    def http_tool(url: str | None = None, method: str = "GET", body: str | None = None) -> str:
        target = (url or (config or {}).get("url") or "").strip()
        if not target:
            return "Error: missing url"
        m = (method or "GET").upper()
        try:
            with httpx.Client(timeout=30.0) as client:
                if m == "GET":
                    r = client.get(target)
                elif m == "POST":
                    r = client.post(target, content=body)
                else:
                    return f"Unsupported method: {m}"
                return f"Status: {r.status_code}\n{r.text[:2000]}"
        except Exception as e:
            return f"Request failed: {e!s}"

    http_tool.__name__ = name.replace(" ", "_")
    http_tool.__doc__ = description or "Call an HTTP endpoint."
    return http_tool


def _make_echo_skill(name: str, description: str) -> Callable[..., str]:
    """占位：仅回显输入，用于自定义 skill 类型。"""

    def echo_tool(text: str) -> str:
        return f"Echo: {text}"

    echo_tool.__name__ = name.replace(" ", "_")
    echo_tool.__doc__ = description or "Echo the input."
    return echo_tool


def skill_from_db_record(skill: Skill) -> Callable[..., Any] | None:
    """把一条 Skill ORM 转为可被 deepagents 使用的 Callable。"""
    config = skill.config or {}
    if skill.type == "http":
        return _make_http_skill(skill.name, skill.description, config)
    if skill.type in ("custom", "echo", ""):
        return _make_echo_skill(skill.name, skill.description)
    return _make_echo_skill(skill.name, skill.description)
