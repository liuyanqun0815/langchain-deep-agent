from pydantic import BaseModel


class AgentConfigOut(BaseModel):
    default_model: str
    planner_model: str | None
    max_tokens: int
    temperature: float


class AgentConfigUpdate(BaseModel):
    default_model: str | None = None
    planner_model: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
