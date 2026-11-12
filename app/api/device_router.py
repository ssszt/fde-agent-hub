from fastapi import APIRouter
from db_tools import get_devices_health_summary

router = APIRouter(prefix="/v1/devices", tags=["Device Health"])

@router.get("/health", summary="获取所有设备最新健康状态与全局告警角标计数")
async def get_devices_health():
  return get_devices_health_summary()
