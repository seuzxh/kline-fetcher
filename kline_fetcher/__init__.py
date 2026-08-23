"""（过渡兼容层）kline-fetcher 统一包已拆分为 tzt-api + kline-qlib。

本包在拆分期间保留旧导入路径：行情类来自 tzt_api，KLineToQlib 暂由根下
converter.py 提供（Task 2 后转发 kline_qlib）。
"""
from tzt_api import (
    AdjustType,
    ConceptPlateFetcher,
    KLineFetcher,
    MinKLineFetcher,
    TrendFetcher,
)
from kline_fetcher.converter import KLineToQlib

__all__ = [
    "KLineFetcher",
    "MinKLineFetcher",
    "ConceptPlateFetcher",
    "TrendFetcher",
    "KLineToQlib",
    "AdjustType",
]
__version__ = "3.0.1"
