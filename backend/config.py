"""应用配置，从环境变量与 .env 读取。"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_skills_root() -> Path:
    """backend 目录下的 skills 目录。"""
    backend_root = Path(__file__).resolve().parent
    return backend_root / "skills"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./data/agent_app_1.db"
    default_model: str = "deepseek-chat"
    planner_model: str | None = None  # 不设则与 default_model 一致
    deepseek_api_key: str = "sk-8972843b6797422a8ed2773896536337"  # 生产环境请用 .env 覆盖
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    openai_base_url: str | None = None  # 兼容本地/代理
    max_tokens: int = 4096
    temperature: float = 0.7
    context_root_dir: str = "./data/context"  # 会话文件系统根目录
    # 技能根目录：backend/skills/，可被 SKILLS_ROOT 环境变量覆盖（绝对路径）
    skills_root: str | None = None

    @property
    def skills_root_dir(self) -> Path:
        if self.skills_root:
            return Path(self.skills_root)
        return _default_skills_root()


settings = Settings()
