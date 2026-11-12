from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.schemas.agent_schema import AgentTaskRequest
from app.services.agent_service import FactoryAgentService

router = APIRouter(prefix="/v1/agent", tags=["Industrial FDE Agent"])

@router.post("/dispatch/stream")
async def dispatch_agent_task_stream(res: AgentTaskRequest):
    try:
        session_id = res.session_id or "default_session"
        provider = res.provider or "gemini"
        return StreamingResponse(
            FactoryAgentService.run_dispatch_loop(res.prompt, session_id=session_id, provider_type=provider),
            media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"流失分发失败: {str(e)}")
