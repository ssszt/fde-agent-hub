import json
from google.genai import types
from app.core.config  import ai_client
from app.tools.factory_tools import create_work_order, send_sms_alert, search_maintenance_sop
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
# 声明派单工具：工单系统闭环
tool_create_work_order = types.FunctionDeclaration(
    name="create_work_order",
    description="在企业工单系统/MES中为异常设备创建维修维保紧急工单。当设备历史运行温度持续高于85°C或存在严重故障状态(如CRITICAL_FAULT)时，必须调用该工具自动派单。",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "device_id": types.Schema(
                type=types.Type.STRING,
                description="故障设备编号,例如 'DEV-003'"
            ),
            "reason": types.Schema(
                type=types.Type.STRING,
                description="故障原因或异常指标描述"
            ),
            "priority": types.Schema(
                type=types.Type.STRING,
                description="工单优先级，可选值为 'NORMAL', 'HIGH', 'EMERGENCY'",
                enum=["NORMAL", "HIGH", "EMERGENCY"]
            )
        },
        required=["device_id", "reason"]
    )
)

# 声明发送告警短信工具
tool_send_sms_alert = types.FunctionDeclaration(
    name="send_sms_alert",
    description="发送短信告警通知到指定手机号，用于通知用户设备异常或工单状态更新。",
    parameters = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "phone": types.Schema(
                type=types.Type.STRING,
                description="用户手机号，例如 '13800000000'"
            ),
            "message": types.Schema(
                type=types.Type.STRING,
                description="要发送的短信内容"
            )
        },
        required=["phone", "message"]
    )
)

#声明维保规程知识库检索工具 (RAG 核心工具)
tool_search_maintenance_sop = types.FunctionDeclaration(
    name="search_maintenance_sop",
    description="在企业私有知识库中检索指定设备的维保标准作业规程(SOP)、应急排查处置步骤与根因分析手册。当设备发生异常或严重故障时，必须调用该工具查询精准排查指南。",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "device_id": types.Schema(
                type=types.Type.STRING,
                description="故障设备编号，例如 'DEV-003'"
            ),
            "query": types.Schema(
                type=types.Type.STRING,
                description="检索关键词或故障现象，例如 '高温超标应急排查' 或 'CRITICAL_FAULT'"
            )
        },
        required=["device_id"]
    )
)
# 仅打包当前已有的这一个工具
factory_tools = types.Tool(
    function_declarations=[tool_query_device_history, tool_create_work_order, tool_send_sms_alert, tool_search_maintenance_sop]
)
class FactoryAgentService:
    @staticmethod
    async def run_dispatch_loop(user_prompt:str) -> tuple[str, list[ToolExecutionTrace]]:
        traces: list[ToolExecutionTrace] = []
        # 将python函数提供给模型作为tools
        config = types.GenerateContentConfig(
            system_instruction=(
                "你是一个工业物联网现场交付工程师专家助手(FDE Agent)。\n"
                "【标准排查作业闭环流程】：\n"
                "1. 当用户要求排查设备时，必须先调用 query_device_history 查询设备的近期历史遥测数据。\n"
                "2. 获得历史数据后，仔细检查：若设备温度高于 85°C 或存在 CRITICAL_FAULT，你必须立即调用 search_maintenance_sop 查询该设备专属的维保应急标准作业规程(SOP)。\n"
                "3. 充分研读 SOP 内容后，调用 create_work_order 派发紧急工单(EMERGENCY)，工单的 reason 中必须概括 SOP 指出的根本原因与处置方向。\n"
                "4. 工单创建成功后，调用 send_sms_alert 向车间主管（手机号 '13800000000'）发送紧急短信通知。\n"
                "5. 最终输出结构严谨的排查终局报告：必须详细罗列 SOP 规程中的具体排查步骤（如阀门编号、工具规格）、安全警告以及已创建的工单号与短信回执。"
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

        # 循环控制：设置 max_turns 熔断保护，防止模型陷入死循环（WLB 保障）
        max_turns = 5
        turn = 0
        current_input:Any = user_prompt
        while turn < max_turns:
            turn += 1
            response_stream = await chat.send_message_stream(current_input)
            pending_tool_calls = []
            async for chunk in response_stream:
                # 拦截模型提出的所有工具调用意图
                if chunk.function_calls:
                    for call in chunk.function_calls:
                        call_name = call.name
                        call_args = dict(call.args)
                        pending_tool_calls.append((call_name, call_args))
                        # SSE 实时通知前端：升起对应的底层调度雷达卡片
                        tool_event_payload = json.dumps({
                            "tool_name": call_name,
                            "arguments": call_args
                        },ensure_ascii=False)
                        yield f"event: tool_call\ndata: {tool_event_payload}\n\n"
                # 拦截普通分析文本，流式推送打字机效果
                text_val = ''
                try:
                    text_val = chunk.text
                except Exception:
                    pass
                if text_val:
                    data = json.dumps({"text": text_val},ensure_ascii=False)
                    yield f"event: delta\ndata: {data}\n\n"
                # 如果这一轮流式结束后，模型没有发起任何工具调用，说明思考和输出完全结束，退出循环
            if not pending_tool_calls:
                break
            # 阶段 3（核心突破）：本地执行物理操作，并将真实结果打包回填给 Gemini 大脑！
            tool_responses = []
            for call_name, call_args in pending_tool_calls:
                if call_name == "query_device_history":
                    device_id = call_args.get("device_id")
                    limit = int(call_args.get("limit", 5))
                    db_result_str = query_device_history(device_id=device_id, limit=limit)
                    print("👉 [1. 大脑向我提出了调用需求]:", call_name, call_args)
                    print("👉 [2. 本地真实查库查到了结果]:", db_result_str)
                    print("👉 [3. 我把结果打包回填给了大脑]")

                    # 将查出的数据推给前端，用于挂载时序趋势图
                    data_payload = json.dumps({
                        "text": f"\n\n**【数据库真实追溯结果】**\n```json\n{db_result_str}\n```\n\n"
                    },ensure_ascii=False)
                    yield f"event: delta\ndata: {data_payload}\n\n"

                    # 格式化并构建 FunctionResponse 回传包
                    try:
                        res_dict = json.loads(db_result_str)
                    except Exception:
                        res_dict = {"raw": db_result_str}
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=call_name,
                            response={"result": res_dict}
                        )
                    )
                elif call_name == "create_work_order":
                    device_id = call_args.get("device_id")
                    reason = call_args.get("reason", "设备运行温度超标")
                    priority = call_args.get("priority", "EMERGENCY")

                    order_result = create_work_order(device_id=device_id, reason=reason, priority=priority)
                    # 构建派单回执的FunctionResponse回传包
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=call_name,
                            response={"result": order_result}
                        )
                    )
                elif call_name == "send_sms_alert":
                    phone = call_args.get("phone")
                    message = call_args.get("message")
                    send_sms_alert(phone, message)
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=call_name,
                            response={"result": f"短信已发送到 {phone}，内容为 {message}"}
                        )
                    )
                elif call_name == "search_maintenance_sop":
                    device_id = call_args.get("device_id")
                    query = call_args.get("query", "高温故障排查")
                    sop_result = search_maintenance_sop(device_id=device_id, query=query)
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=call_name,
                            response={"result": sop_result}
                        )
                    )
                # 将这轮的工具执行结果作为下一轮输入，送入 chat 进行二轮自主推理！
            current_input = tool_responses
            
     
