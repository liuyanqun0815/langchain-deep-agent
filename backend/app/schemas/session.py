from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SessionCreate(BaseModel):
    title: str | None = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    config: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class SessionListResponse(BaseModel):
    items: list[SessionOut]
    total: int


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    role: str
    content: str
    metadata_: dict[str, Any] | None = None
    created_at: datetime


class MessageCreate(BaseModel):
    user_message: str


class InferenceStep(BaseModel):
    """单条推理/工具调用步骤，用于推理框展示。"""
    kind: str  # "thinking" | "tool_call" | "tool_result"
    name: str | None = None  # 工具/技能名
    content: str = ""  # 思考内容、参数摘要或结果摘要


class SendMessageResponse(BaseModel):
    role: str = "assistant"
    content: str
    message_id: int
    created_at: datetime
    inference_steps: list[InferenceStep] = []
