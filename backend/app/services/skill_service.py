"""技能 CRUD 与同步到 Agent 注册表；支持从本地路径、GitHub 动态添加。"""

import shutil
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from config import settings
from app.db.models import Skill
from app.schemas.skill import SkillOut
from app.agent.skills.registry import skill_registry
from app.agent.skills.loader import import_github_repo_skills, parse_skill_manifest
from app.agent.skills.sync import sync_skills_from_disk
from app.agent.factory import rebuild_agent


def list_skills(db: Session) -> list[SkillOut]:
    skills = list(db.exec(select(Skill).order_by(Skill.id)).all())
    return [SkillOut.model_validate(s) for s in skills]


def _is_absolute_path(path_str: str) -> bool:
    """判断是否为绝对路径（Windows 盘符或 Unix /）。"""
    p = path_str.strip()
    if not p:
        return False
    path = Path(p)
    return path.is_absolute()


def _copy_skill_from_absolute_path(abs_path: Path, skills_root: Path) -> str:
    """
    将绝对路径指向的技能目录递归复制到 backend/skills/<dir_name>/。
    使用 shutil.copytree 复制目录内所有文件和子文件夹（完整目录树）。
    返回复制后的相对路径（用于 source_path），如 docx。
    """
    if not abs_path.is_dir():
        raise ValueError(f"路径不存在或不是目录: {abs_path}")
    dest_name = abs_path.name
    dest_dir = skills_root / dest_name
    skills_root.mkdir(parents=True, exist_ok=True)
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    # copytree 递归复制：所有文件、子目录及其内容
    shutil.copytree(abs_path, dest_dir)
    return dest_name


def add_skill_from_local(db: Session, source_path: str) -> Skill | None:
    """
    从本地路径添加技能（需存在 skill.yaml 或 SKILL.md）。
    支持两种路径格式：
    - 相对路径：backend/skills/ 下的子目录名，如 example_skill
    - 绝对路径：如 E:\\chrome_downloads\\skills-main\\skills\\docx，会将内容复制到 skills/<dir_name>/
    """
    skills_root = settings.skills_root_dir
    path_str = source_path.strip()

    if _is_absolute_path(path_str):
        abs_path = Path(path_str).resolve()
        dest_name = _copy_skill_from_absolute_path(abs_path, skills_root)  # raises ValueError if invalid
        source_path = dest_name
        skill_dir = skills_root / dest_name
    else:
        skill_dir = skills_root / path_str.lstrip("/")
        if not skill_dir.is_dir():
            return None

    # 需有 skill.yaml（可注册为 Tool）或 SKILL.md（官方技能，仅复制供 Agent 按需加载）
    has_yaml = any((skill_dir / n).exists() for n in ("skill.yaml", "skill.yml", "skill.json"))
    has_skill_md = (skill_dir / "SKILL.md").exists()
    if not has_yaml and not has_skill_md:
        return None

    manifest = parse_skill_manifest(skill_dir)
    # 无论 skill.yaml 还是 SKILL.md，均写入 DB（便于删除/启用/禁用）
    return _add_skill_record(db, skill_dir, source_path, manifest)


def _add_skill_record(db, skill_dir, source_path, manifest: dict | None) -> Skill | None:
    name = str(manifest.get("name", skill_dir.name)).strip() if manifest else skill_dir.name

    existing = db.exec(select(Skill).where(Skill.source_type == "local", Skill.source_path == source_path)).first()
    if existing:
        existing.description = str(manifest.get("description", "")) if manifest else ""
        existing.type = str(manifest.get("type", "python"))[:64] if manifest else "python"
        existing.enabled = True
        db.add(existing)
        db.commit()
        db.refresh(existing)
        rebuild_agent()
        return existing

    s = Skill(
        name=name,
        description=str(manifest.get("description", "")) if manifest else "",
        type=str(manifest.get("type", "python"))[:64] if manifest else "python",
        config=manifest.get("config") if manifest and isinstance(manifest.get("config"), dict) else None,
        source_type="local",
        source_path=source_path,
        enabled=True,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    rebuild_agent()
    return s


def add_skill_from_github(db: Session, repo_url: str) -> list[Skill]:
    """
    从 GitHub 仓库导入技能：

    - 仅复制仓库中 `skills/` 目录下的技能子目录到当前项目根目录 `skills/`
    - 一个仓库可包含多个技能，每个技能作为独立开关（独立 Skill 记录）
    """
    skills_root = settings.skills_root_dir
    imported_paths = import_github_repo_skills(repo_url, skills_root)
    created_or_updated: list[Skill] = []

    for source_path in imported_paths:
        skill_dir = skills_root / source_path
        manifest = parse_skill_manifest(skill_dir)
        name = str(manifest.get("name", source_path)).strip() if manifest else source_path
        description = str(manifest.get("description", "") if manifest else "")
        skill_type = str(manifest.get("type", "python"))[:64] if manifest else "python"
        config = manifest.get("config") if manifest and isinstance(manifest.get("config"), dict) else None

        existing = db.exec(select(Skill).where(Skill.source_type == "github", Skill.source_path == source_path)).first()
        if existing:
            existing.name = name
            existing.description = description
            existing.type = skill_type
            existing.config = config
            # 逐个开关：导入后默认不强制开启
            db.add(existing)
            db.commit()
            db.refresh(existing)
            created_or_updated.append(existing)
            continue

        s = Skill(
            name=name,
            description=description,
            type=skill_type,
            config=config,
            source_type="github",
            source_path=source_path,
            enabled=False,
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        created_or_updated.append(s)

    rebuild_agent()
    return created_or_updated


def get_skill(db: Session, skill_id: int) -> Skill | None:
    return db.get(Skill, skill_id)


def toggle_skill(db: Session, skill_id: int, enabled: bool) -> Skill | None:
    s = db.get(Skill, skill_id)
    if s is None:
        return None
    s.enabled = enabled
    s.updated_at = datetime.utcnow()
    db.add(s)
    db.commit()
    db.refresh(s)
    rebuild_agent()
    return s


def delete_skill(db: Session, skill_id: int) -> bool:
    """
    删除技能：移除 DB 记录；若为 local/github 来源则同时删除磁盘目录。
    返回是否删除成功。
    """
    s = db.get(Skill, skill_id)
    if s is None:
        return False
    skills_root = settings.skills_root_dir
    if s.source_type in ("local", "github") and s.source_path:
        skill_dir = skills_root / s.source_path
        if skill_dir.exists() and skill_dir.is_dir():
            shutil.rmtree(skill_dir)
    db.delete(s)
    db.commit()
    rebuild_agent()
    return True
