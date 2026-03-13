"""FastAPI 应用入口：挂载路由、初始化 DB 与 Agent。"""

import os
import logging
from contextlib import asynccontextmanager

import dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
dotenv.load_dotenv()
# Agent 执行与技能加载日志输出到 stdout
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("APP_DEBUG", "0") == "1" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("app.agent").setLevel(logging.INFO)
logging.getLogger("app.services.agent_service").setLevel(logging.INFO)

# 关键运行时日志（建议只在本地/测试开启 DEBUG）
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.error").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
logging.getLogger("deepagents").setLevel(logging.DEBUG if os.environ.get("APP_DEBUG", "0") == "1" else logging.INFO)
logging.getLogger("langchain").setLevel(logging.DEBUG if os.environ.get("APP_DEBUG", "0") == "1" else logging.INFO)
logging.getLogger("langchain_core").setLevel(logging.DEBUG if os.environ.get("APP_DEBUG", "0") == "1" else logging.INFO)
logging.getLogger("httpx").setLevel(logging.INFO)

# 开启 LangChain 调试/verbose 与 LangSmith（仅在本地/DEBUG 环境下）
if os.environ.get("LANGCHAIN_DEBUG", "0") == "1" or os.environ.get("APP_DEBUG", "0") == "1":
    from langchain_core.globals import set_debug, set_verbose

    set_verbose(True)
    logging.getLogger(__name__).info("LangChain debug/verbose enabled")

    # LangSmith 配置：仅在 DEBUG 模式自动开启

    os.environ.setdefault(
        "LANGSMITH_API_KEY",
        os.environ.get("LANGSMITH_API_KEY"),
    )
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    logging.getLogger(__name__).info("LangSmith tracing enabled in debug mode")

from config import settings
from app.db.session import init_db
from app.agent.factory import get_agent
from app.agent.skills.registry import skill_registry
from app.agent.skills.sync import sync_skills_from_disk
from app.routers import sessions, skills, models, agent_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings.skills_root_dir.mkdir(parents=True, exist_ok=True)
    sync_skills_from_disk()
    skill_registry.reload_from_db()
    get_agent()
    yield
    # shutdown if needed


app = FastAPI(title="DeepAgent Demo", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(skills.router)
app.include_router(models.router)
app.include_router(agent_config.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
