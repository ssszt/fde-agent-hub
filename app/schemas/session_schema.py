from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict

class SessionItem(BaseModel):
  session_id: str
  title: str
  created_at: str
  updated_at: str

class CreateSessionRequest(BaseModel):
  session_id: Optional[str] = Field(None, decription="可选，不传则系统自动生成短 ID")
  title: Optional[str] = Field("新排查会话", description="会话标题")

class UpdateSessionRequest(BaseModel):
  title: str = Field(..., min_length=1, max_length=50, description="新会话标题")

class MessageItem(BaseModel):
  id: int
  session_id: str
  role: str
  content: str
  tool_calls: Optional[List[Dict[str, Any]]] = None
  created_at: str

class SessionMessagesResponse(BaseModel):
  session_id: str
  messages: List[MessageItem]
