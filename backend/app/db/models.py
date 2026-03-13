"""SQLModel ORM 模型：Session, Message, Skill。"""

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class Session(SQLModel, table=True):
    __tablename__ = "sessions"
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(default="新会话", max_length=512)
    config: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Message(SQLModel, table=True):
    __tablename__ = "messages"
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="sessions.id", index=True)
    role: str = Field(max_length=32)
    content: str = Field(sa_column=Column(Text))
    metadata_: dict[str, Any] | None = Field(default=None, sa_column=Column("metadata", JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Skill(SQLModel, table=True):
    __tablename__ = "skills"
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=128, index=True)
    description: str = Field(default="", sa_column=Column(Text))
    type: str = Field(default="custom", max_length=64)
    config: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    enabled: bool = Field(default=True, index=True)
    # 来源：builtin=内置配置, local=本地目录, github=GitHub 仓库
    source_type: str = Field(default="builtin", max_length=32)
    # 本地为相对 skills 根目录的子路径；github 为仓库 URL 或克隆后的子路径
    source_path: str | None = Field(default=None, max_length=512)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
