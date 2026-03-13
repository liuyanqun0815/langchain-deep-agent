from typing import Any

from pydantic import BaseModel, ConfigDict


class SkillCreate(BaseModel):
    name: str
    description: str = ""
    type: str = "custom"
    config: dict[str, Any] | None = None
    source_type: str = "builtin"
    source_path: str | None = None


class SkillAddFromLocal(BaseModel):
    """从本地路径添加技能。支持相对路径（backend/skills/ 子目录名）或绝对路径。"""

    source_path: str  # 相对路径如 my_skill，或绝对路径如 E:\downloads\skills\docx


class SkillAddFromGitHub(BaseModel):
    """从 GitHub 仓库添加技能（仓库根目录需有 skill.yaml 或 SKILL.md）。"""

    repo_url: str  # 如 https://github.com/owner/repo 或 owner/repo


class SkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    type: str
    config: dict[str, Any] | None
    enabled: bool
    source_type: str
    source_path: str | None
    created_at: Any
    updated_at: Any


class SkillToggle(BaseModel):
    enabled: bool
