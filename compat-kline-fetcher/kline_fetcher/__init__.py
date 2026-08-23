"""kline-fetcher（deprecated 兼容壳，3.1.0 终版）。

原统一包已拆分（2026-08）：
  - 行情请求 → tzt-api（tzt_api 包）
  - qlib 写入 → kline-qlib（kline_qlib 包）

本包仅为旧导入路径提供转发，不再演进；请逐步迁移：
    from kline_fetcher import KLineFetcher      →  from tzt_api import KLineFetcher
    from kline_fetcher import KLineToQlib       →  from kline_qlib import KLineToQlib
    from kline_fetcher.fetcher import ...       →  from tzt_api import ...（或 tzt_api._base）
    from kline_fetcher.converter import ...     →  from kline_qlib.converter import ...
    from kline_fetcher.download import ...      →  from kline_qlib.download import ...
    uvicorn kline_fetcher.server:app            →  uvicorn kline_qlib.server:app
"""
from tzt_api import (
    AdjustType,
    ConceptPlateFetcher,
    KLineFetcher,
    MinKLineFetcher,
    TrendFetcher,
)
from kline_qlib import KLineToQlib

__all__ = [
    "KLineFetcher",
    "MinKLineFetcher",
    "ConceptPlateFetcher",
    "TrendFetcher",
    "KLineToQlib",
    "AdjustType",
]
__version__ = "3.1.0"
