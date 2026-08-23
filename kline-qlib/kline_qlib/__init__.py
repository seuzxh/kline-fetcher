"""kline-qlib：K线行情 → qlib bin 数据管道。

依赖方向：→ tzt-api（行情获取与市场规则）。本包不含 HTTP 客户端实现。
"""
from kline_qlib.converter import KLineToQlib, QLIB_DAY_FIELDS, QLIB_MIN_FIELDS
from kline_qlib.download import (
    POOL_MAP,
    download_day_kline,
    download_min_kline,
    load_stock_pool,
)

__all__ = [
    "KLineToQlib",
    "QLIB_DAY_FIELDS",
    "QLIB_MIN_FIELDS",
    "POOL_MAP",
    "load_stock_pool",
    "download_day_kline",
    "download_min_kline",
]
__version__ = "1.0.0"
