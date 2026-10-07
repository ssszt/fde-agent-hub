import json
from google.genai import types
from app.core.config  import ai_client
from app.tools.factory_tools import AVAILABLE_TOOLS
from app.schemas.agent_schema import ToolExecutionTrace
from db_tools import query_device_history


# 声明查库工具
tool_query_device_history = types.FunctionDeclaration(
    name = "query_device_history",
    description="查询指定设备的历史运行温度、时间戳和状态记录，用于排查设备故障趋势或历史异常。",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "device_id": types.Schema(
                type=types.Type.STRING,
                description="设备的唯一标识符，例如 'DEV-003'"
            ),
            "limit": types.Schema(
                type=types.Type.NUMBER,
                description="要返回的历史记录数量，默认 5 条"
            )
        },
        required=["device_id"]
    )
)
# 仅打包当前已有的这一个工具
factory_tools = types.Tool(
    function_declarations=[tool_query_device_history]
)
class FactoryAgentService:
    @staticmethod
    async def run_dispatch_loop(user_prompt:str) -> tuple[str, list[ToolExecutionTrace]]:
        traces: list[ToolExecutionTrace] = []
        # 将python函数提供给模型作为tools
        config = types.GenerateContentConfig(
            system_instruction=(
                "你是一个工业物联网现场交付工程师助手(FDE Agent)。"
                "当用户提及设备排查时，你必须先调用 get_device_telemetry 获取真实指标。"
                "若指标超出阈值（如温度高于85度或有故障码），必须调用 create_work_order 派发工单。"
                "最终根据拿到的所有数据输出结构清晰的排查结论。"
            ),
            tools=[factory_tools],
            temperature=0.2,
        )
        # 使用sdk的chats模块维持会话上下文
        chat = ai_client.aio.chats.create(model="gemini-2.5-flash", config=config)
        # 发送请求，sdk会在底层自动处理工具调用并回填结果
        # response = await chat.send_message(user_prompt)
        # history = chat.get_history()
        # 提取历史调用轨迹
        # for message in history:
        #     for part in message.parts:
        #         if part.function_call:
        #             traces.append(ToolExecutionTrace(
        #                 tool_name=part.function_call.name,
        #                 arguments=dict(part.function_call.args),
        #                 output="Executed by runtime"
        #             ))
        # return response.text, traces
        response_stream = await chat.send_message_stream(user_prompt)
        async for chunk in response_stream:
            # 阶段1 拦截模型发出的工具调用指令（告诉前端正在执行什么动作）
            if chunk.function_calls:
                for call in chunk.function_calls:
                    call_name = call.name
                    call_args = dict(call.args)
                    tool_event_payload = json.dumps({
                        "tool_name": call_name,
                        "arguments": call_args
                    },ensure_ascii=False)
                    yield f"event: tool_call\ndata: {tool_event_payload}\n\n"
                    # 执行真实本地sqllite穿透查询
                    if call_name == "query_device_history":
                        device_id = call_args.get("device_id")
                        limit = call_args.get("limit", 5)
                        db_result_str = query_device_history(device_id=device_id, limit=limit)
                        # 将查出的原始 JSON 数据直接追加推给前端
                        data_payload = json.dumps({
                            "text": f"\n\n**【数据库真实追溯结果】**\n```json\n{db_result_str}\n```\n\n"
                        }, ensure_ascii=False)
                        yield f"event: delta\ndata: {data_payload}\n\n"
                    # data = json.dumps({"tool_name": fc.name,"arguments": dict(fc.args)})
                    # yield f"event: tool_call\ndata:{data}\n\n"
            #阶段2 拦截模型的最终分析文本（告诉前端模型在说什么， 实现打字机效果）
            text_val = ""
            try:
                text_val = chunk.text
            except:
                pass
            if text_val:
                data = json.dumps({"text": text_val},ensure_ascii=False)
                yield f"event: delta\ndata: {data}\n\n"
            
     
