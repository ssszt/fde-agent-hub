from fastapi import APIRouter, HTTPException
from app.schemas.agent_schema import AgentTaskRequest, AgentTaskResponse
from app.services.agent_service import FactoryAgentService

router = APIRouter(prefix="/v1/agent", tags=["Industrial FDE Agent"])

@router.post("/dispatch", response_model=AgentTaskResponse)

async def dispatch_agent_task(req:AgentTaskRequest):
    try:
        final_text, traces = await FactoryAgentService.run_dispatch_loop(req.prompt)
        return AgentTaskResponse(
            success=True,
            final_analysis=final_text,
            traces=traces
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"智能体执行失败: {str(e)}")