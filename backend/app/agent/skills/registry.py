"""按需加载技能：仅从 local/github 磁盘目录加载；仅加载 enabled=True 的技能。"""

from typing import Callable

from sqlmodel import Session, select

from config import settings
from app.db.models import Skill
from app.db.session import engine
from app.agent.skills.loader import load_skill_from_path


def _load_tools_from_db_and_disk() -> list[Callable[..., object]]:
    """从 DB 中加载 enabled 技能，仅 local/github 有 source_path 的从磁盘加载。"""
    skills_root = settings.skills_root_dir
    with Session(engine) as session:
        statement = select(Skill).where(Skill.enabled == True)  # noqa: E712
        skills = list(session.exec(statement).all())
    tools: list[Callable[..., object]] = []
    for s in skills:
        if s.source_type in ("local", "github") and s.source_path:
            fn = load_skill_from_path(skills_root, s.source_path)
            if fn is not None:
                tools.append(fn)
    return tools


class SkillRegistry:
    """维护当前已启用的 skill 对应的工具列表；reload 时从 DB + 磁盘重新加载。"""

    def __init__(self) -> None:
        self._tools: list[Callable[..., object]] = []

    def reload_from_db(self) -> list[Callable[..., object]]:
        self._tools = _load_tools_from_db_and_disk()
        return self._tools

    def get_tools(self) -> list[Callable[..., object]]:
        if not self._tools:
            self.reload_from_db()
        return self._tools.copy()


skill_registry = SkillRegistry()
