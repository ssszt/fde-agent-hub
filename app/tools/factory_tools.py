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
        device_id: device_id,
        "status": "DISPATCHED",
        "priority": priority,
        "reason": reason,
        "message": f"工单 {order_id} 已成功分发至现场值班工程师"
    }

# 将工具注册为一个全局列表供大模型绑定使用
AVAILABLE_TOOLS = [get_device_telemetry, create_work_order]