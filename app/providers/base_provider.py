"""
双轨大模型抽象契约层 (LLM Provider Interface & Contract)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, AsyncGenerator
from app.tools.registry import ToolResult

@dataclass
class ToolCallIntent:
  """
  大模型触发的标准化工具调用意图
  抹平 Google GenAI (call.name/call.args) 与 OpenAI/Ollama (function.name/arguments) 的差异
  """
  tool_name: str
  arguments: Dict[str, Any]
  call_id: Optional[str] = None # Ollama/OpenAI 协议所需的调用上下文 ID


@dataclass
class StreamChunk:
  """
  统一的流式输出增量块
  """
  delta_text: str = ""
  tool_calls: List[ToolCallIntent] = field(default_factory=list)
  raw_chunk: Any =  None # 保留底层原始响应供调试

class BaseLLMSession(ABC):

  @abstractmethod
  async def send_message_stream(self, current_input: Any) -> AsyncGenerator[StreamChunk, None]:
    """
    发送用户提问或多轮工具回执，返回统一的流式增量生成器
    :param current_input: 第一轮为 str（用户提问），后续轮次为 List[Tuple[ToolCallIntent, ToolResult]]
    """
    pass

class BaseLLMProvider(ABC):

  @property
  @abstractmethod
  def provider_name(self) -> str:
    """返回供应商唯一标识，如 'gemini' | 'ollama'"""
    pass

  @abstractmethod
  def get_or_create_session(self, session_id: str, system_instruction: str,history_messages: Optional[List[Dict[str, Any]]] = None) -> BaseLLMSession:
    """
    从历史记忆中恢复或新建一个活跃会话实例
    """
    pass
