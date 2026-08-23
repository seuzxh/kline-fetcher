#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""（过渡兼容垫片）实现已迁至 kline_qlib.converter。新代码：from kline_qlib import KLineToQlib"""
from kline_qlib.converter import KLineToQlib, QLIB_DAY_FIELDS, QLIB_MIN_FIELDS

__all__ = ["KLineToQlib", "QLIB_DAY_FIELDS", "QLIB_MIN_FIELDS"]
