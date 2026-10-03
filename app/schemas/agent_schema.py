from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class AgentTaskRequest(BaseModel):
    prompt: str = Field(..., example="3号机 (DEV-003) 疑似过热，帮我查一下遥测状态，如果严重立刻派紧急工单")

class ToolExecutionTrace(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    output: Any
class AgentTaskResponse(BaseModel):
    success: bool
    final_analysis: str
    traces: List[ToolExecutionTrace]