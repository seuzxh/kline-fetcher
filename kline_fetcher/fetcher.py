#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""向后兼容垫片：保持 `from kline_fetcher.fetcher import KLineFetcher` 可用。

v2.1.0 起，原 fetcher.py（792 行）已按职责拆分为：
  - kline_fetcher._base.KLineFetcher                基类 + 日K线方法
  - kline_fetcher.min_kline.MinKLineFetcher          分钟K线方法（继承 KLineFetcher）
  - kline_fetcher.concept_plate.ConceptPlateFetcher  概念板块方法（继承 KLineFetcher）

本文件仅为兼容旧导入路径保留。新代码请直接从对应模块导入：
    from kline_fetcher import KLineFetcher, MinKLineFetcher, ConceptPlateFetcher
"""

from kline_fetcher._base import (
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

__all__ = [
    "KLineFetcher",
    "AdjustType",
    "ADJUST_MAP",
    "_resolve_adjust",
    "PRICE_SCALE",
    "TURNOVER_SCALE",
    "MARKET_CODE_MAP",
    "KLINE_TYPE_MAP",
    "KLINE_RESPONSE_KEY_MAP",
]
