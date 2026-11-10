"""
Gemini 官方大模型适配器
"""
from typing import Any, AsyncGenerator, Optional, Dict, List, Tuple
from google.genai import types
from app.core.config  import ai_client
from app.tools.registry import tool_registry, ToolResult
from app.providers.base_provider import (
  BaseLLMProvider,
  BaseLLMSession,
  StreamChunk,
  ToolCallIntent
)

class GeminiSession(BaseLLMSession):
  """
  基于 Google GenAI Chat 实例的会话包装器
  """
  def __init__(self, chat_instance: Any):
    self._chat = chat_instance
  async def send_message_stream(self, current_input: Any) -> AsyncGenerator[StreamChunk, None]:
    """
    统一流式交互中枢：
    - 若输入为用户字符串（第 1 轮），直接发送
    - 若输入为上一轮的工具执行结果（第 2+ 轮），在此处自动转译为 Gemini 专有的 types.Part 回执
    """
    gemini_input: Any = current_input
    # 核心转换，如果是工具执行结果列表
    if isinstance(current_input,list):
      gemini_parts = []
      for item in current_input:
        if isinstance(item, tuple) and len(item) == 2:
          call_intent, tool_result = item
          tool_name = call_intent.tool_name if hasattr(call_intent, 'tool_name') else str(call_intent)
          # 按照Gemini规范包装response payload
          if isinstance(tool_result.result_data, dict) and "result" in tool_result.result_data:
            payload = tool_result.result_data
          else:
            payload = {"result": tool_result.result_data}
          # 此处将通用的ToolResult优雅转换为Gemini SDK专有的types.part
          part = types.Part.from_function_response(
            name=tool_name,
            response=payload
          )
          gemini_parts.append(part)
      if not gemini_parts:
        return
      gemini_input = gemini_parts
      # 调用底层流式通信
      response_stream = await self._chat.send_message_stream(gemini_input)
      async for chunk in response_stream:
        tool_intents: List[ToolCallIntent] = []
        
        # 1.拦截模型发起的工具调用
        if chunk.function_calls:
          for call in chunk.function_calls:
            tool_intents.append(
              ToolCallIntent(
                tool_name= call.name,
                arguments= dict(call.args)
              )
            )
      # 2.提取文本增量
      text_val = ''
      try:
          text_val = chunk.text or ""
      except Exception:
        # 当 chunk 只包含工具调用时，读取 chunk.text 可能会抛出异常，安全忽略
        pass
      # 3.产出统一的标准数据块StreamChunk
      if text_val or tool_intents:
        yield StreamChunk(
          delta_text=text_val,  
          tool_calls=tool_intents,
          raw_chunk=chunk
        )

class GeminiProvider(BaseLLMProvider):
  """
  Gemini 供应商驱动工厂
  """
  def __init__(self, model_name: str="gemini-2.5-flash", temperature: float = 0.2):
    self._model_name = model_name
    self._temperature = temperature
    self._sessions: Dict[str, GeminiSession] = {}
  @property
  def provider_name(self) -> str:
    return "gemini"
    
  def get_or_create_session(self, session_id: str, system_instruction: str,history_messages: Optional[List[Dict[str, Any]]] = None) -> BaseLLMSession:
    """
    从内存或数据库审计流水中重建 Gemini 会话上下文（Context Rehydration）
    """
    if session_id in self._sessions:
      return self._sessions[session_id]
    rehydrated_history: List[types.Content] = []
    if history_messages:
      for msg in history_messages:
        # 转换角色用户是 user，助手在 Gemini SDK 中必须为 model
        gemini_role ="user" if msg["role"] == "user" else "model"
        if msg.get("content"):
          rehydrated_history.append(
            types.Content(
              role=gemini_role,
              parts=[types.Part.from_text(text=msg["content"])]
            )
          )
      # 🛡️ 防御性守卫：Gemini 要求 history 必须以 model 结尾（或者为空）
      # 若历史最后一条是不幸悬空的 user，将其剔除以确保模型交替律不报错
      if rehydrated_history and rehydrated_history[-1].role == "user":
        rehydrated_history.pop()
    
    config = types.GenerateContentConfig(
      system_instruction = system_instruction,
      tools=tool_registry.get_gemini_tools(),
      temperature=self._temperature,
    )

    chat_instance = ai_client.aio.chats.create(
      model=self._model_name,
      config=config,
      history=rehydrated_history if rehydrated_history else None
    )
    session = GeminiSession(chat_instance)
    self._sessions[session_id] = session
    return session


