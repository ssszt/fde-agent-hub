"""
【架构关系图解】：
- 依赖基类：app.providers.base_provider.BaseLLMProvider (统一接口)
- 聚合驱动：GeminiProvider (云端) 与 LocalProvider (本地)
- 核心职责：依据请求动态路由，管理 Provider 实例单例，实现即插即用
"""

from typing import Dict
from app.providers.base_provider import BaseLLMProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.local_provider import LocalProvider

class LLMProviderFactory:
  """
  单例驱动工厂：避免重复初始化 Provider
  """
  _providers: Dict[str, BaseLLMProvider] = {}

  @classmethod
  def get_provider(cls, provider_type: str="gemini") -> BaseLLMProvider:
    """
    获取指定的大模型供应商驱动
    :param provider_type: 'gemini' | 'local' | 'ollama'
    """
    key = (provider_type or "gemini").lower()
    if key == "ollama":
      key = "local"
    
    if key not in cls._providers:
      if key == "local":
        print("⚡ [ProviderFactory] 激活【本地私有化模型引擎 (Local / Ollama)】")
        cls._providers[key] = LocalProvider()
      
      else:
        print("☁️ [ProviderFactory] 激活【云端旗舰模型引擎 (Google Gemini)】")
        cls._providers[key] = GeminiProvider()
    return cls._providers[key]

