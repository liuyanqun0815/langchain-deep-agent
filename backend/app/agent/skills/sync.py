"""启动时将 skills 目录下发现的本地技能同步到 DB（仅新增，不覆盖已有）。"""

from pathlib import Path

from sqlmodel import Session, select

from config import settings
from app.db.models import Skill
from app.db.session import engine
from app.agent.skills.loader import discover_local_skills


def sync_skills_from_disk() -> int:
    """
    扫描 skills 根目录，将带有 skill.yaml 的子目录作为本地技能写入 DB（若尚不存在）。
    返回新增或更新的技能数量。
    """
    skills_root = settings.skills_root_dir
    skills_root.mkdir(parents=True, exist_ok=True)
    discovered = discover_local_skills(skills_root)
    if not discovered:
        return 0
    count = 0
    with Session(engine) as session:
        for manifest in discovered:
            source_path = manifest.get("source_path")
            if not source_path:
                continue
            name = str(manifest.get("name", source_path)).strip()
            existing = session.exec(
                select(Skill).where(Skill.source_type == "local", Skill.source_path == source_path)
            ).first()
            if existing:
                # 可选：用 manifest 更新 description/type
                existing.description = str(manifest.get("description", existing.description))
                existing.type = str(manifest.get("type", existing.type))[:64]
                session.add(existing)
                count += 1
                continue
            # 避免同名内置技能冲突：仅当无同 source_path 时新增
            existing_by_path = session.exec(
                select(Skill).where(Skill.source_path == source_path)
            ).first()
            if existing_by_path:
                continue
            skill = Skill(
                name=name,
                description=str(manifest.get("description", "")),
                type=str(manifest.get("type", "python"))[:64],
                config=manifest.get("config") if isinstance(manifest.get("config"), dict) else None,
                source_type="local",
                source_path=source_path,
                enabled=True,
            )
            session.add(skill)
            count += 1
        session.commit()
    return count
