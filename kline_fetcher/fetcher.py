#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""向后兼容垫片：保持 `from kline_fetcher.fetcher import ...` 可用。

行情实现已迁至 tzt-api 包（历史：v2.1.0 单文件拆分为多模块，本次拆包）。
本垫片同时补上 TrendFetcher（v2.1.0 拆分时的遗漏）。
新代码推荐：
    from tzt_api import KLineFetcher, MinKLineFetcher, ConceptPlateFetcher, TrendFetcher
"""

from tzt_api._base import (
    KLineFetcher,
    AdjustType,
    ADJUST_MAP,
    _resolve_adjust,
    PRICE_SCALE,
    TURNOVER_SCALE,
    MARKET_CODE_MAP,
    KLINE_TYPE_MAP,
    KLINE_RESPONSE_KEY_MAP,
)
from tzt_api.min_kline import MinKLineFetcher
from tzt_api.concept_plate import ConceptPlateFetcher
from tzt_api.trend import TrendFetcher

__all__ = [
    "KLineFetcher",
    "MinKLineFetcher",
    "ConceptPlateFetcher",
    "TrendFetcher",
    "AdjustType",
    "ADJUST_MAP",
    "_resolve_adjust",
    "PRICE_SCALE",
    "TURNOVER_SCALE",
    "MARKET_CODE_MAP",
    "KLINE_TYPE_MAP",
    "KLINE_RESPONSE_KEY_MAP",
]
