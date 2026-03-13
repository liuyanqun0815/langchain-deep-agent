"""技能 CRUD、toggle、从本地/GitHub 动态添加 API。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.skill import SkillOut, SkillToggle, SkillAddFromLocal, SkillAddFromGitHub
from app.services import skill_service

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("", response_model=list[SkillOut])
def list_skills(db: Session = Depends(get_session)) -> list[SkillOut]:
    return skill_service.list_skills(db)


@router.post("/from-local")
def add_from_local(
    body: SkillAddFromLocal,
    db: Session = Depends(get_session),
):
    """
    从本地路径添加技能。支持：
    - 相对路径：backend/skills/ 下的子目录名，如 example_skill
    - 绝对路径：如 E:\\skills\\docx，会将内容复制到 backend/skills/docx/
    """
    try:
        s = skill_service.add_skill_from_local(db, body.source_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if s is None:
        raise HTTPException(
            status_code=400,
            detail="路径不存在或缺少 skill.yaml/SKILL.md，请提供有效技能目录",
        )
    return SkillOut.model_validate(s)


@router.post("/from-github", response_model=list[SkillOut])
def add_from_github(
    body: SkillAddFromGitHub,
    db: Session = Depends(get_session),
) -> list[SkillOut]:
    """从 GitHub 仓库导入技能：复制 repo/skills/* 到当前 skills/，并逐个生成开关。"""
    try:
        skills = skill_service.add_skill_from_github(db, body.repo_url)
        return [SkillOut.model_validate(s) for s in skills]
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{skill_id}/toggle", response_model=SkillOut)
def toggle_skill(
    skill_id: int,
    body: SkillToggle,
    db: Session = Depends(get_session),
) -> SkillOut:
    s = skill_service.toggle_skill(db, skill_id, body.enabled)
    if s is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return SkillOut.model_validate(s)


@router.delete("/{skill_id}")
def delete_skill(skill_id: int, db: Session = Depends(get_session)):
    """删除技能（含 local/github 的磁盘目录）。"""
    ok = skill_service.delete_skill(db, skill_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"ok": True}
