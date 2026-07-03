from web.routes.chat import router as chat_router
from web.routes.model import router as model_router
from web.routes.agent import router as agent_router
from web.routes.skill import router as skill_router

__all__ = ["chat_router", "model_router", "agent_router", "skill_router"]
