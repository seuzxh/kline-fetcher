"""tzt-api：中焯行情 3.0 API 客户端（A股日K/分钟K/概念板块/分时）。

公开 API：
    KLineFetcher           — 基类（日K线 + 共享底座）
    MinKLineFetcher        — 分钟K线（继承 KLineFetcher）
    ConceptPlateFetcher    — 概念板块（继承 KLineFetcher）
    TrendFetcher           — 分时数据（继承 KLineFetcher）
    AdjustType             — 复权方式枚举

市场规则（与 kline-qlib 共享的单一事实源）见 tzt_api.market。
qlib 数据转换/下载见 kline-qlib 包。
"""
from tzt_api._base import KLineFetcher, AdjustType
from tzt_api.min_kline import MinKLineFetcher
from tzt_api.concept_plate import ConceptPlateFetcher
from tzt_api.trend import TrendFetcher

__all__ = [
    "KLineFetcher",
    "MinKLineFetcher",
    "ConceptPlateFetcher",
    "TrendFetcher",
    "AdjustType",
]
__version__ = "1.0.0"
