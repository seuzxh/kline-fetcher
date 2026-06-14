"""kline-fetcher：A股K线数据获取与qlib格式转换工具。

公开 API：
    KLineFetcher           — 基类（日K线 + 共享底座）
    MinKLineFetcher        — 分钟K线（继承 KLineFetcher）
    ConceptPlateFetcher    — 概念板块（继承 KLineFetcher）
    KLineToQlib            — K线数据转 qlib bin 格式
    AdjustType             — 复权方式枚举
"""
from kline_fetcher._base import KLineFetcher, AdjustType
from kline_fetcher.min_kline import MinKLineFetcher
from kline_fetcher.concept_plate import ConceptPlateFetcher
from kline_fetcher.converter import KLineToQlib

__all__ = [
    "KLineFetcher",
    "MinKLineFetcher",
    "ConceptPlateFetcher",
    "KLineToQlib",
    "AdjustType",
]
__version__ = "2.1.0"
