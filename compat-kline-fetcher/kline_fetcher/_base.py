"""兼容垫片，实现位于 tzt_api（`kline_fetcher._base` 旧导入路径转发）。"""
from tzt_api._base import (  # noqa: F401
    KLineFetcher, AdjustType, ADJUST_MAP, _resolve_adjust,
    PRICE_SCALE, TURNOVER_SCALE, MARKET_CODE_MAP, KLINE_TYPE_MAP,
    KLINE_RESPONSE_KEY_MAP, INDEX_CODE_MAP, INDEX_CODE_PREFIXES,
)
