import json
from google.genai import types
from app.core.config  import ai_client
from app.tools.factory_tools import AVAILABLE_TOOLS
from app.schemas.agent_schema import ToolExecutionTrace

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
            temperature=0.1,
            tools=AVAILABLE_TOOLS
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
                for fc in chunk.function_calls:
                    data = json.dumps({"tool_name": fc.name,"arguments": dict(fc.args)})
                    yield f"event: tool_call\ndata:{data}\n\n"
            #阶段2 拦截模型的最终分析文本（告诉前端模型在说什么， 实现打字机效果）
            text_val = ""
            try:
                text_val = chunk.text
            except:
                pass
            if text_val:
                data = json.dumps({"text": text_val},ensure_ascii=False)
                yield f"event: delta\ndata: {data}\n\n"
            
     
