#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_build_min_arrays 单元测试：覆盖 #3「缺 time 字段静默丢数据」修复。

无需真实 API 或文件系统：构造 KLineToQlib 实例后手动注入 min_cal_to_idx，
直接调用内部方法 _build_min_arrays 验证行为。
"""
import logging
import os
import tempfile

import numpy as np

from kline_qlib.converter import KLineToQlib


def _make_converter(freq="5min"):
    """构造一个空日历的 converter（用临时目录避免读到真实 QLIB_DATA_DIR）。"""
    with tempfile.TemporaryDirectory() as tmp:
        conv = KLineToQlib(qlib_data_dir=tmp)
        # 注入一个最小的分钟日历，便于 _build_min_arrays 索引查找
        timestamps = [
            "2026-06-13 09:30:00",
            "2026-06-13 09:35:00",
            "2026-06-13 09:40:00",
            "2026-06-13 09:45:00",
        ]
        conv.min_cal_to_idx[freq] = {ts: i for i, ts in enumerate(timestamps)}
        conv.min_calendars[freq] = timestamps
        # 返回前复制一份属性（临时目录出作用域后路径失效，但我们不再访问文件）
        return conv


def _sample_kline(date, time_str, close=10.0):
    return {
        "date": date,
        "time": time_str,
        "open": close, "high": close, "low": close, "close": close,
        "volume": 1000, "amount": close * 1000, "factor": 1.0,
    }


class TestBuildMinArraysMissingTime:
    def test_missing_time_field_is_skipped_not_silently_dropped(self, caplog):
        """#3 修复核心：缺 time 字段的条目应被跳过 + 打 warning，而非用 00:00:00 回退后静默丢失。"""
        conv = _make_converter("5min")
        kline_data = [
            _sample_kline("2026-06-13", "09:30:00", close=10.0),
            # 第 2 条故意去掉 time 字段 —— 旧行为会用 00:00:00，索引查不到，静默丢
            {k: v for k, v in _sample_kline("2026-06-13", "09:35:00", close=11.0).items() if k != "time"},
            _sample_kline("2026-06-13", "09:40:00", close=12.0),
        ]

        with caplog.at_level(logging.WARNING, logger="KLineToQlib"):
            arrays = conv._build_min_arrays(kline_data, freq="5min")

        # 1. 有 warning 报告跳过条数
        assert any("缺少 time 字段" in r.message for r in caplog.records), \
            "缺 time 字段时应打 warning"
        skip_msg = [r.message for r in caplog.records if "缺少 time 字段" in r.message][0]
        assert "1/3" in skip_msg, f"warning 应报告跳过比例，实际: {skip_msg}"

        # 2. 缺 time 的那条确实没写入（close=11.0 不应出现在结果里）
        close_arr = arrays["close"]
        assert 11.0 not in close_arr.tolist(), "缺 time 的数据不应被写入"

        # 3. 有 time 的两条正常写入
        # min_idx=0 (09:30), 数据覆盖 idx 0,2（跳过 idx 1=09:35 那条）
        # 数组长度 = max_idx - min_idx + 1 = 2 - 0 + 1 = 3
        # close = [10.0, NaN, 12.0]
        assert close_arr[0] == 10.0
        assert np.isnan(close_arr[1])  # 09:35 位置：缺 time 那条 + 本就无数据
        assert close_arr[2] == 12.0

    def test_no_warning_when_all_have_time(self, caplog):
        """所有条目都有 time 字段时，不应打 missing-time warning。"""
        conv = _make_converter("5min")
        kline_data = [
            _sample_kline("2026-06-13", "09:30:00"),
            _sample_kline("2026-06-13", "09:35:00"),
        ]

        with caplog.at_level(logging.WARNING, logger="KLineToQlib"):
            conv._build_min_arrays(kline_data, freq="5min")

        assert not any("缺少 time 字段" in r.message for r in caplog.records), \
            "所有条目都有 time 时不应打 missing-time warning"

    def test_empty_time_string_treated_as_missing(self, caplog):
        """空字符串 time 也应视为缺失（falsy 判断）。"""
        conv = _make_converter("5min")
        kline_data = [
            {"date": "2026-06-13", "time": "",  # 空字符串
             "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "amount": 1, "factor": 1},
        ]

        with caplog.at_level(logging.WARNING, logger="KLineToQlib"):
            result = conv._build_min_arrays(kline_data, freq="5min")

        # 全部缺 time → 触发 "No valid timestamps" 的 None 返回
        assert result is None
        assert any("缺少 time 字段" in r.message for r in caplog.records)
