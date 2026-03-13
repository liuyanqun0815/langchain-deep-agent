"""会话与消息 API。"""

from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from config import settings
from app.db.session import get_session
from app.schemas.session import (
    SessionCreate,
    SessionOut,
    SessionListResponse,
    MessageOut,
    MessageCreate,
    SendMessageResponse,
)
from app.services import session_service
from app.services import agent_service

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut)
def create_session(
    body: SessionCreate | None = None,
    db: Session = Depends(get_session),
) -> SessionOut:
    data = SessionCreate(title=body.title) if body else None
    s = session_service.create_session(db, data)
    return SessionOut.model_validate(s)


@router.get("", response_model=SessionListResponse)
def list_sessions(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_session),
) -> SessionListResponse:
    return session_service.list_sessions(db, limit=limit, offset=offset)


@router.get("/{session_id}", response_model=dict)
def get_session_detail(
    session_id: int,
    db: Session = Depends(get_session),
) -> dict:
    s, messages = session_service.get_session_with_messages(db, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session": SessionOut.model_validate(s),
        "messages": [MessageOut.model_validate(m) for m in messages],
    }


@router.post("/{session_id}/messages", response_model=SendMessageResponse)
def send_message(
    session_id: int,
    body: MessageCreate,
    db: Session = Depends(get_session),
) -> SendMessageResponse:
    s = session_service.get_session_by_id(db, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    content, message_id, created_at, inference_steps = agent_service.chat(db, session_id, body.user_message)
    return SendMessageResponse(
        role="assistant",
        content=content,
        message_id=message_id,
        created_at=created_at,
        inference_steps=inference_steps,
    )


@router.post("/{session_id}/messages/stream")
def send_message_stream(
    session_id: int,
    body: MessageCreate,
    db: Session = Depends(get_session),
):
    """
    流式对话接口：
    - 使用 Server-Sent Events (text/event-stream) 将 Agent 的增量回复推给前端；
    - 前端可通过 EventSource 订阅此接口，逐步渲染回复内容。
    """
    s = session_service.get_session_by_id(db, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")

    generator = agent_service.chat_stream(db, session_id, body.user_message)
    return StreamingResponse(generator, media_type="text/event-stream")


async def _save_uploaded_files(session_id: int, files: List[UploadFile]) -> list[dict[str, str]]:
    """
    将上传的文件保存到会话专属目录：
    data/uploads/session_{id}/filename
    返回包含 name/path 的文件信息列表。
    """
    if not files:
        return []
    uploads_root = Path("data/uploads")
    session_dir = uploads_root / f"session_{session_id}"
    session_dir.mkdir(parents=True, exist_ok=True)
    infos: list[dict[str, str]] = []
    for f in files:
        content = await f.read()
        dest = session_dir / f.filename
        dest.write_bytes(content)
        infos.append({"name": f.filename, "path": str(dest)})
    return infos


@router.post("/{session_id}/messages/upload", response_model=SendMessageResponse)
async def send_message_with_files(
    session_id: int,
    user_message: str = Form(...),
    files: List[UploadFile] = File(default_factory=list),
    db: Session = Depends(get_session),
) -> SendMessageResponse:
    """支持文件上传的对话接口：文本 + 多文件。"""
    s = session_service.get_session_by_id(db, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    files_info = await _save_uploaded_files(session_id, files)
    content, message_id, created_at, inference_steps = agent_service.chat_with_files(
        db, session_id, user_message, files_info
    )
    return SendMessageResponse(
        role="assistant",
        content=content,
        message_id=message_id,
        created_at=created_at,
        inference_steps=inference_steps,
    )


@router.delete("/{session_id}", status_code=204)
def delete_session(
    session_id: int,
    db: Session = Depends(get_session),
) -> None:
    """删除单个会话及其消息。"""
    ok = session_service.delete_session(db, session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")


@router.delete("", status_code=204)
def delete_all_sessions(
    db: Session = Depends(get_session),
) -> None:
    """删除所有会话（谨慎操作，可用于一键清空）。"""
    session_service.delete_all_sessions(db)
