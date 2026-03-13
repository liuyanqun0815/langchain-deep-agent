"""会话文件系统上下文：为每个 session 维护逻辑工作目录。"""

import os
from pathlib import Path

from config import settings


def get_session_context_dir(session_id: int) -> str:
    """返回某会话的上下文根目录路径（用于本地存储时）。"""
    root = Path(settings.context_root_dir)
    root.mkdir(parents=True, exist_ok=True)
    return str(root / f"session_{session_id}")
