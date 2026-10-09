from typing import Dict, Any

def get_device_telemetry(device_id: str) -> Dict[str, Any]:
    """
    根据设备ID查询车间设备的实时遥测数据和传感器指标。
    
    参数:
        device_id: 设备唯一编号，例如 'DEV-001', 'DEV-003'
    """
    # 模拟真实工业设备数据库查询
    mock_db = {
        "DEV-001": {"status": "NORMAL", "temperature": 42.1, "pressure": 4.5, "error_code": None},
        "DEV-003": {"status": "CRITICAL_FAULT", "temperature": 96.8, "pressure": 13.2, "error_code": "E-401"},
    }

    return mock_db.get(
        device_id,
        {"status": "UNKNOWN", "temperature": 0.0, "pressure": 0.0, "error_code": "DEVICE_NOT_FOUND"}
    )

def create_work_order(device_id: str, reason: str, priority: str="NORMAL") -> Dict[str, Any]:
    """
    在企业工单系统/MES中创建设备维修维保工单。
    
    参数:
        device_id: 故障设备编号
        reason: 故障原因或异常指标描述
        priority: 工单优先级，可选值为 'NORMAL', 'HIGH', 'EMERGENCY'
    """
    # 模拟工单落库与派发动作
    import random
    order_id = f"WO-20261003-{random.randint(100, 999)}"

    return {
        "order_id": order_id,
        "device_id": device_id,
        "status": "DISPATCHED",
        "priority": priority,
        "reason": reason,
        "message": f"工单 {order_id} 已成功分发至现场值班工程师"
    }

def send_sms_alert(phone: str, message: str) -> None:
    """
    模拟发送短信通知用户。
    
    参数:
        phone: 用户手机号
        message: 要发送的短信内容
    """
    # 模拟短信发送动作
    print(f"发送短信到 {phone}，内容为 {message}")
    return None


# ==========================================
# 企业私有维保知识库 (SOP 知识库)
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

def search_maintenance_sop(device_id: str, query: str = "") -> Dict[str, Any]:
    """
    在企业私有 SOP 知识库中根据设备编号检索对应的标准检修处置规程。
    """
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
AVAILABLE_TOOLS = [get_device_telemetry, create_work_order, send_sms_alert, search_maintenance_sop]
