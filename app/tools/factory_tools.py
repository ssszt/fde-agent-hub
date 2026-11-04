import json
import random
from typing import Dict, Any
from google.genai import types

from db_tools import query_device_history
from app.tools.registry import register_tool, ToolResult
# ==========================================
# 工具 1：物理时序遥测查库工具 (适配层)
# ==========================================
@register_tool(
    name="query_device_history", # 给 Gemini 大脑识别的唯一契约名（与 Prompt 对齐）
    description="查询指定设备的历史运行温度、时间戳和状态记录，用于排查设备故障趋势或历史异常。",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "device_id": types.Schema(
                type=types.Type.STRING,
                description="设备唯一编号，例如 'DEV-001', 'DEV-003'"
            )
        },
        required=["device_id"]
    )
)
def query_device_history_tool(device_id: str, limit: int=5) -> ToolResult:
    """
    智能体适配工具：调用 db_tools 中的底层纯函数，封装 Generative UI 标记并返回 ToolResult
    """
    db_result_str = query_device_history(device_id=device_id, limit=limit)
    try:
        res_dict = json.loads(db_result_str)
    except Exception:
        res_dict = {"raw": db_result_str}
    # 封装前端暗黑时序看板所需的 Markdown/JSON 标记
    display_payload = f"\n\n**【数据库真实追溯结果】**\n```json\n{db_result_str}\n```\n\n"
    return ToolResult(
        result_data=res_dict,
        display_text=display_payload
    )

# ==========================================
# 工具 2：MES/工单系统紧急派单工具
# ==========================================
@register_tool(
    name="create_work_order",
    description="在企业工单系统/MES中为异常设备创建维修维保紧急工单。当设备历史运行温度持续高于85°C或存在严重故障状态(如CRITICAL_FAULT)时，必须调用该工具自动派单。",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "device_id": types.Schema(
                type=types.Type.STRING,
                description="故障设备编号，例如'DEV-003'"
            ),
            "reason": types.Schema(
                type=types.Type.STRING,
                description="故障原因或异常指标描述"
            ),
            "priority": types.Schema(
                type=types.Type.STRING,
                description="工单优先级，可选值为 'NORMAL', 'HIGH', 'EMERGENCY'"
            )
        },
        required=["device_id", "reason"]
    )
)
def create_work_order(device_id: str, reason: str, priority: str="EMERGENCY") -> Dict[str, Any]:
    order_id = f"WO-20261003-{random.randint(100, 999)}"
    return {
        "order_id": order_id,
        "device_id": device_id,
        "status": "DISPATCHED",
        "priority": priority,
        "reason": reason,
        "message": f"工单 {order_id} 已成功分发至现场值班工程师"
    }
# ==========================================
# 工具 3：现场运维短信告警工具
# ==========================================
@register_tool(
    name="send_sms_alert",
    description="发送短信告警通知到指定手机号，用于通知用户设备异常或工单状态更新。",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "phone": types.Schema(
                type=types.Type.STRING,
                description="用户手机号"
            ),
            "message": types.Schema(
                type=types.Type.STRING,
                description="要发送的短信内容"
            )
        },
        required=["phone", "message"]
    )
)
def send_sms_alert(phone: str, message: str) -> Dict[str, Any]:
    # 💥 【混沌注入】：模拟第三方短信网关突发连接重置崩溃！
    # raise ConnectionResetError("电信运营商 SMS 网关报 503 临时熔断，Socket 连接被重置！")
    print(f"发送短信到 {phone}，内容为 {message}")
    return {
        "status": "SENT",
        "phone": phone,
        "receipt": f"发送短信到 {phone}，内容为 {message},回执确认通过"
    }
# ==========================================
# 工具 4：企业私有维保 SOP 知识库检索工具 (RAG)
# ==========================================
SOP_KNOWLEDGE_BASE = {
    "DEV-003": [
        {
            "sop_id": "SOP-DEV003-COOLING-01",
            "title": "DEV-003 冷却系统高温异常与故障码 E-401 应急处置规程",
            "trigger_condition": "温度持续高于 85°C 或 伴随 CRITICAL_FAULT 报警",
            "root_cause_analysis": "历史统计显示 85% 为次级冷却回路 P-102 离心泵电机过载保护跳闸，或旁通电磁阀 V-08 卡滞导致水循环中断。",
            "action_steps": [
                "步骤 1: 穿戴防烫手套，将中控柜操作旋钮切至【MANUAL-手动检修】安全模式，严禁直接强行拉下主进线电源闸刀。",
                "步骤 2: 携带 14 号梅花扳手，逆时针旋转 90 度松开次级管路旁通阀 V-08 螺栓，观察有无高温气塞现象并完成机械泄压。",
                "步骤 3: 检查冷却液回水滤网 S-04，清理金属碎屑堆积；若滤网压差表指针处于红区，需立即进行反冲洗或备件更换。",
                "步骤 4: 测量水泵 P-102 端子相间阻值，若三相阻值偏差超过 5%，需向仓储中心领用备用电机（型号: MTR-2200-B）实施总成更换。"
            ],
            "safety_warning": "冷却管路内部残存蒸汽压力可达 0.6MPa，泄压前严禁拆卸快拆接头！"
        }
    ],
    "DEV-001": [
        {
            "sop_id": "SOP-DEV001-MAINT-01",
            "title": "DEV-001 主轴常规温度偏高巡检保养规程",
            "trigger_condition": "温度处于 50~65°C 正常浮动范围",
            "root_cause_analysis": "通常为机油润滑不畅或环境散热不良。",
            "action_steps": [
                "步骤 1: 检查 ISO VG 32 主轴润滑油油位视窗是否低于最低刻度线。",
                "步骤 2: 清理电柜底部进风格栅滤网。"
            ],
            "safety_warning": "常规保养请在停机 10 分钟后进行。"
        }
    ]
}

@register_tool(
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
def search_maintenance_sop(device_id: str, query: str = "") -> Dict[str, Any]:
    records = SOP_KNOWLEDGE_BASE.get(device_id, [])
    if not records:
        return{
            "found": False,
            "device_id": device_id,
            "message": f"未在知识库中检索到设备 {device_id} 的专用维护规程"
        }
     # 模拟精确命中该设备的应急排查 SOP
    matched_sop = records[0]
    return {
        "found": True,
        "device_id": device_id,
        "sop_id": matched_sop["sop_id"],
        "title": matched_sop["title"],
        "trigger_condition": matched_sop["trigger_condition"],
        "root_cause": matched_sop["root_cause_analysis"],
        "action_steps": matched_sop["action_steps"],
        "safety_warning": matched_sop["safety_warning"]
    }
# 将工具注册为一个全局列表供大模型绑定使用
# AVAILABLE_TOOLS = [get_device_telemetry, create_work_order, send_sms_alert, search_maintenance_sop]
