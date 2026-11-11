import inspect
from dataclasses import dataclass
from typing import Any, Callable,Dict,Optional,List
from google.genai import types

@dataclass
class ToolResult:
  """
  标准工具执行回执规范（Tool Execution Result Contract）

  属性说明：
  - result_data: 回填给模型大脑进行多轮推理的数据（任意结构：dict, str, list等）
  - display_text: 可选，专门用于通过SSE delta 增量推送给前端的渲染标记（如 Generative UI 的 JSON 时序标记）
  - is_error: 工具执行是否遇到异常
  - error_message: 异常详细信息
  """
  result_data: Any
  display_text: Optional[str] = None
  is_error: bool = False
  error_message: Optional[str] = None

@dataclass
class ToolDefinition:
  """
  工具定义实体：封装工具名称、模型契约声明与底层执行函数
  """
  name: str
  description: str
  parameters: types.Schema
  func: Callable

@dataclass
class ToolRegistry:
  """
  生产级工具注册中心工厂（Enterprise Tool Registry Factory）

  核心职责：
  1.提供@registry_tool装饰器语法，实现工具声明与实现的自洽内聚
  2.集中到处符合 Google GenAI SDK 格式的 Tool 列表
  3.充当执行沙箱与安全防波堤，统一拦截异常并降级回填
  """

  def __init__(self):
    self._tools: Dict[str, ToolDefinition] = {}

  def register(self, name:str, description:str, parameters: types.Schema) -> Callable:
    """
    工具注册装饰器

    用法示例：
    @register_tool(
        name="query_device_history",
        description="查询设备历史数据",
        parameters=types.Schema(...)
    )
    def query_device_history(device_id: str, limit: int = 5):
        ...
    """
    def decorator(func: Callable) -> Callable:
      tool_def = ToolDefinition(
        name=name,
        description=description,
        parameters=parameters,
        func=func
      )
      self._tools[name] = tool_def
      return func
    return decorator
  
  def get_tools(self, name:str) -> Optional[ToolDefinition]:
    """获取指定工具定义"""
    return self._tools.get(name)

  def list_tools(self) -> List[ToolDefinition]:
    """列出所有已注册工具定义"""
    return list(self._tools.values())

  def get_gemini_tools(self) -> List[types.Tool]:
    """
    导出满足 Google GenAI SDK 契约的 tools 参数
    注意：必须返回 List[types.Tool]，避免之前遇到的元组解包报错！
    """
    declarations = [
      types.FunctionDeclaration(
        name=t.name,
        description=t.description,
        parameters=t.parameters
      )
      for t in self.list_tools()
    ]
    return [types.Tool(function_declarations=declarations)]

  async def dispatch(self, tool_name:str,arguments: Dict[str, Any]) -> ToolResult:
    """
    统一分发执行与安全防波堤 (Error Boundary)
    执行逻辑：
    1.检查工具是否存在，若未注册，返回降级错误，不崩溃
    2.兼容执行异步或同步函数
    3.自动适配返回值，支持裸数据与定制ToolResult
    4.统一拦截异常并包装为降级回执回填给大模型
    # 5.自动组装 Gemini genai 的types.Part.from_function_response。
    """
    if tool_name not in self._tools:
      err_msg = f"未注册的工具：'{tool_name}',请确认工具名称是否正确"
      return ToolResult(
        result_data={"status": "error", "error_type": "ToolNotFound", "message": err_msg},
        is_error=True,
        error_message=err_msg
      )
      # part = types.Part.from_function_response(
      #   name=tool_name,
      #   response={'result': tool_result.result_data }
      # )
      # return tool_result, part
    tool_def = self._tools[tool_name]
    try:
      # 兼容异步与同步函数
      if inspect.iscoroutinefunction(tool_def.func):
        raw_output = await tool_def.func(**arguments)
      else:
        raw_output = tool_def.func(**arguments)
      # 自动适配返回值结构
      if isinstance(raw_output, ToolResult):
        tool_result = raw_output
      else:
        tool_result = ToolResult(result_data=raw_output)
    except Exception as e:
      # 安全防波堤：捕获所有底层异常并优雅包装
      err_msg = f"工具 [{tool_name}] 运行时异常: {str(e)}"
      print(f"⚠️ [ToolRegistry 防波堤拦截异常] {err_msg}")
      tool_result = ToolResult(
        result_data={
          "status": "error",
          "error_type": type(e).__name__,
          "message": err_msg,
          "suggestion": "该工具执行受阻，请评估当前异常是否可跳过，或在最终排查结论中向工程师进行异常警示。"
        },
        is_error=True,
        error_message=err_msg
      )
    # 构造回填给Gemini大脑的标准part
    if isinstance(tool_result.result_data, dict) and "result" in tool_result.result_data:
      response_payload = tool_result.result_data
    else:
      response_payload = {"result": tool_result.result_data}

    # part = types.Part.from_function_response(
    #   name=tool_name,
    #   response=response_payload
    # )

    return tool_result
# 全局单例注册中心实例
tool_registry = ToolRegistry()
register_tool = tool_registry.register
