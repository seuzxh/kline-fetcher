#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""（过渡兼容垫片）实现已迁至 kline_qlib.download。新代码：from kline_qlib import download_day_kline"""
from kline_qlib.download import (
    POOL_MAP,
    download_day_kline,
    download_min_kline,
    load_stock_pool,
    main,
)

__all__ = [
    "POOL_MAP",
    "load_stock_pool",
    "download_day_kline",
    "download_min_kline",
    "main",
]
