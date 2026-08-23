#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""（兼容垫片）`uvicorn kline_fetcher.server:app` 仍可用，实现位于 kline_qlib.server。"""
from kline_qlib.server import app, main

__all__ = ["app", "main"]
