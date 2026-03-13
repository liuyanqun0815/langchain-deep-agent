"""创建 deepagents Agent（含 planner、文件系统、长期记忆、tools、官方 SKILL.md 技能）。"""

import logging
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, LocalShellBackend, StoreBackend
from deepagents.backends.filesystem import FilesystemBackend
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from config import settings
from app.agent.skills.registry import skill_registry

logger = logging.getLogger(__name__)

_agent_graph: Any = None
_store: InMemoryStore | None = None
_checkpointer: MemorySaver | None = None


def _get_skill_paths_for_agent() -> list[str]:
    """
    扫描 skills 根目录下包含 SKILL.md 的子目录，返回供 create_deep_agent(skills=...) 使用的路径列表。
    符合 [Agent Skills 规范](https://agentskills.io/specification)，与官方文档一致。
    """
    root = settings.skills_root_dir
    if not root.is_dir():
        return []
    paths: list[str] = []
    for path in root.iterdir():
        if path.is_dir() and not path.name.startswith("."):
            if (path / "SKILL.md").exists():
                paths.append(f"/skills/{path.name}/")
    return paths


def _make_backend(runtime: Any) -> CompositeBackend:
    skills_root = settings.skills_root_dir
    # backend/data/uploads：上文上传文件的临时目录，Agent 可通过 /uploads/ 访问
    uploads_root = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
    routes = {"/memories/": StoreBackend(runtime)}
    if skills_root.is_dir():
        routes["/skills/"] = FilesystemBackend(root_dir=skills_root, virtual_mode=True)
    if uploads_root.is_dir():
        routes["/uploads/"] = FilesystemBackend(root_dir=uploads_root, virtual_mode=True)
    # LocalShellBackend：支持 execute 执行本地 shell，root_dir=backend 目录
    # 注意：仅用于本地开发，生产环境需使用沙箱（BaseSandbox）或 HITL 审批
    backend_root = Path(__file__).resolve().parent.parent.parent
    logger.info("LocalShellBackend enabled: %s", backend_root)
    local_shell = LocalShellBackend(
        root_dir=backend_root,
        inherit_env=True,
    )
    return CompositeBackend(
        default=local_shell,
        routes=routes,
    )


def _build_agent() -> Any:
    import os

    model_id = settings.default_model.strip().lower()
    if model_id.startswith("deepseek") or model_id == "deepseek-chat":
        os.environ.setdefault("DEEPSEEK_API_KEY", settings.deepseek_api_key)
        from langchain_deepseek import ChatDeepSeek

        model = ChatDeepSeek(
            model="deepseek-chat",
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
        )
    else:
        try:
            from langchain.chat_models import init_chat_model

            model = init_chat_model(
                model=settings.default_model,
                temperature=settings.temperature,
                max_tokens=settings.max_tokens,
            )
        except ImportError:
            from langchain_openai import ChatOpenAI

            model = ChatOpenAI(
                model=settings.default_model.split(":")[-1] if ":" in settings.default_model else settings.default_model,
                temperature=settings.temperature,
                max_tokens=settings.max_tokens,
            )

    tools = skill_registry.get_tools()
    skill_paths = _get_skill_paths_for_agent()
    if skill_paths:
        logger.info("DeepAgent skills (SKILL.md) loaded: %s", skill_paths)
    # system_prompt = """你是一个智能办公助手。"""
    global _store, _checkpointer, _agent_graph
    _store = InMemoryStore()
    _checkpointer = MemorySaver()
    create_kw: dict[str, Any] = dict(
        model=model,
        tools=tools,
        # system_prompt=system_prompt,
        store=_store,
        backend=_make_backend,
        checkpointer=_checkpointer,
    )
    if skill_paths:
        create_kw["skills"] = ["/skills/"]
    _agent_graph = create_deep_agent(**create_kw)
    return _agent_graph


def get_agent() -> Any:
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = _build_agent()
    return _agent_graph


def rebuild_agent() -> Any:
    """在配置或 skills 变更后重建 Agent。"""
    global _agent_graph
    skill_registry.reload_from_db()
    _agent_graph = _build_agent()
    return _agent_graph
