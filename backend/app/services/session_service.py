"""会话与消息的 CRUD。"""

from datetime import datetime

from sqlalchemy import delete
from sqlmodel import Session, select

from app.db.models import Session as SessionModel, Message, MessageRole
from app.schemas.session import SessionCreate, SessionOut, MessageOut, SessionListResponse


def create_session(db: Session, data: SessionCreate | None = None) -> SessionModel:
    title = (data.title if data else None) or "新会话"
    s = SessionModel(title=title)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def list_sessions(db: Session, limit: int = 50, offset: int = 0) -> SessionListResponse:
    statement = select(SessionModel).order_by(SessionModel.updated_at.desc()).limit(limit).offset(offset)
    items = list(db.exec(statement).all())
    count_statement = select(SessionModel)
    total = len(list(db.exec(count_statement).all()))
    return SessionListResponse(items=[SessionOut.model_validate(x) for x in items], total=total)


def get_session_by_id(db: Session, session_id: int) -> SessionModel | None:
    return db.get(SessionModel, session_id)


def get_session_with_messages(db: Session, session_id: int) -> tuple[SessionModel | None, list[MessageOut]]:
    s = get_session_by_id(db, session_id)
    if s is None:
        return None, []
    statement = select(Message).where(Message.session_id == session_id).order_by(Message.created_at.asc())
    messages = list(db.exec(statement).all())
    out = []
    for m in messages:
        o = MessageOut.model_validate(m)
        if hasattr(m, "metadata_"):
            setattr(o, "metadata_", getattr(m, "metadata_", None))
        out.append(o)
    return s, out


def update_session_title(db: Session, session_id: int, title: str) -> SessionModel | None:
    s = db.get(SessionModel, session_id)
    if s is None:
        return None
    s.title = title
    s.updated_at = datetime.utcnow()
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def add_message(db: Session, session_id: int, role: str, content: str, metadata: dict | None = None) -> Message:
    m = Message(session_id=session_id, role=role, content=content, metadata_=metadata)
    db.add(m)
    db.commit()
    db.refresh(m)
    s = db.get(SessionModel, session_id)
    if s:
        s.updated_at = datetime.utcnow()
        db.add(s)
        db.commit()
    return m


def ensure_session_title_from_first_message(db: Session, session_id: int, first_user_content: str) -> None:
    s = db.get(SessionModel, session_id)
    if not s or s.title != "新会话":
        return
    title = (first_user_content[:50] + "…") if len(first_user_content) > 50 else first_user_content or "新会话"
    update_session_title(db, session_id, title)


def delete_session(db: Session, session_id: int) -> bool:
    """删除单个会话及其全部消息。"""
    s = db.get(SessionModel, session_id)
    if s is None:
        return False
    db.exec(delete(Message).where(Message.session_id == session_id))
    db.delete(s)
    db.commit()
    return True


def delete_all_sessions(db: Session) -> None:
    """删除所有会话及其消息。"""
    db.exec(delete(Message))
    db.exec(delete(SessionModel))
    db.commit()
