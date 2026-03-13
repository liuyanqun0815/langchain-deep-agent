"""Agent 配置读写 API。"""

from fastapi import APIRouter

from config import settings
from app.schemas.agent_config import AgentConfigOut, AgentConfigUpdate
from app.agent.factory import rebuild_agent

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.get("/config", response_model=AgentConfigOut)
def get_config() -> AgentConfigOut:
    return AgentConfigOut(
        default_model=settings.default_model,
        planner_model=settings.planner_model,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
    )


@router.put("/config", response_model=AgentConfigOut)
def update_config(body: AgentConfigUpdate) -> AgentConfigOut:
    if body.default_model is not None:
        settings.default_model = body.default_model
    if body.planner_model is not None:
        settings.planner_model = body.planner_model
    if body.max_tokens is not None:
        settings.max_tokens = body.max_tokens
    if body.temperature is not None:
        settings.temperature = body.temperature
    rebuild_agent()
    return AgentConfigOut(
        default_model=settings.default_model,
        planner_model=settings.planner_model,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
    )
