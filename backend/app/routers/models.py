"""模型列表与测试 API。"""

from fastapi import APIRouter

from config import settings

router = APIRouter(prefix="/api/models", tags=["models"])

MOCK_MODELS = [
    {"id": "deepseek-chat", "name": "deepseek-chat", "provider": "deepseek", "description": "DeepSeek 聊天模型（默认）"},
    {"id": "openai:gpt-4o-mini", "name": "gpt-4o-mini", "provider": "openai", "description": "OpenAI 小模型"},
    {"id": "openai:gpt-4o", "name": "gpt-4o", "provider": "openai", "description": "OpenAI 主力模型"},
    {"id": "anthropic:claude-sonnet-4-20250514", "name": "claude-sonnet-4", "provider": "anthropic", "description": "Anthropic Claude"},
]


@router.get("", response_model=list)
def list_models() -> list:
    return MOCK_MODELS


@router.post("/test")
def test_model() -> dict:
    """调用当前配置的模型发一条简单请求，验证连通性。"""
    try:
        from app.agent.factory import get_agent

        agent = get_agent()
        result = agent.invoke(
            {"messages": [{"role": "user", "content": "Reply with exactly: OK"}]},
            config={"configurable": {"thread_id": "test-ping"}},
        )
        msgs = result.get("messages", [])
        last = msgs[-1] if msgs else None
        content = getattr(last, "content", None) or (last.get("content") if isinstance(last, dict) else None)
        return {"success": True, "message": str(content)[:200]}
    except Exception as e:
        return {"success": False, "message": str(e)}
