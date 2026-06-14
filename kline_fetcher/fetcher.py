#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""向后兼容垫片：保持 `from kline_fetcher.fetcher import ...` 可用。

v2.1.0 起，原 fetcher.py（792 行）已按职责拆分为：
  - kline_fetcher._base.KLineFetcher                基类 + 日K线方法
  - kline_fetcher.min_kline.MinKLineFetcher          分钟K线方法（继承 KLineFetcher）
  - kline_fetcher.concept_plate.ConceptPlateFetcher  概念板块方法（继承 KLineFetcher）

本文件兼容 v2.1.0 前的导入路径，导出全部公开类与常量。
新代码推荐从包入口导入：
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
from kline_fetcher.min_kline import MinKLineFetcher
from kline_fetcher.concept_plate import ConceptPlateFetcher

__all__ = [
    "KLineFetcher",
    "MinKLineFetcher",
    "ConceptPlateFetcher",
    "AdjustType",
    "ADJUST_MAP",
    "_resolve_adjust",
    "PRICE_SCALE",
    "TURNOVER_SCALE",
    "MARKET_CODE_MAP",
    "KLINE_TYPE_MAP",
    "KLINE_RESPONSE_KEY_MAP",
]
