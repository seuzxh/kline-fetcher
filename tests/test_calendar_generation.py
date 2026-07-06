#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日历生成函数边界单测（#9 修复验证）。

验证 _generate_1min_timestamps / _generate_5min_timestamps 生成的时刻集合：
- 含 11:30（上午收盘）、15:00（全天收盘）—— #9 修复的关键
- 不含 09:30、13:00（API 不返回这两个时刻数据）
- 条数正确（1min=240, 5min=50）
"""
import pytest

from kline_fetcher.converter import KLineToQlib

DATE = "2026-06-12"


class TestGenerate1minTimestamps:
    def gen(self):
        return KLineToQlib._generate_1min_timestamps(DATE, 240, "1min")

    def test_count(self):
        """1min 每天 240 条（09:31~11:30 = 120, 13:01~15:00 = 120）。"""
        ts = self.gen()
        assert len(ts) == 240, f"期望 240 条，实际 {len(ts)}"

    def test_contains_morning_close_1130(self):
        """含 11:30（上午收盘）—— #9 修复关键。"""
        ts = self.gen()
        assert f"{DATE} 11:30:00" in ts, "应含 11:30 上午收盘"

    def test_contains_afternoon_close_1500(self):
        """含 15:00（全天收盘）—— #9 修复关键。"""
        ts = self.gen()
        assert f"{DATE} 15:00:00" in ts, "应含 15:00 全天收盘"

    def test_not_contains_open_0930(self):
        """不含 09:30（API 不返回该时刻数据）。"""
        ts = self.gen()
        assert f"{DATE} 09:30:00" not in ts

    def test_not_contains_afternoon_open_1300(self):
        """不含 13:00（API 不返回该时刻数据）。"""
        ts = self.gen()
        assert f"{DATE} 13:00:00" not in ts

    def test_not_contains_after_1500(self):
        """不含 15:00 之后（如 15:01）。"""
        ts = self.gen()
        assert f"{DATE} 15:01:00" not in ts

    def test_not_contains_before_0930(self):
        """不含 09:30 之前（如 09:29）。"""
        ts = self.gen()
        assert f"{DATE} 09:29:00" not in ts

    def test_sorted_and_contiguous(self):
        """时间戳连续递增，步长 1 分钟（中间无断点）。"""
        ts = self.gen()
        # 解析为分钟数，验证上午/下午段内连续
        def to_minutes(s):
            t = s.split(" ")[1]
            h, m = int(t[:2]), int(t[3:5])
            return h * 60 + m

        mins = [to_minutes(s) for s in ts]
        # 上午段：09:31(571) ~ 11:30(690)，应连续
        morning = [m for m in mins if 571 <= m <= 690]
        assert morning == list(range(571, 691)), "上午段应 09:31~11:30 连续"
        # 下午段：13:01(781) ~ 15:00(900)，应连续
        afternoon = [m for m in mins if 781 <= m <= 900]
        assert afternoon == list(range(781, 901)), "下午段应 13:01~15:00 连续"


class TestGenerate5minTimestamps:
    def gen(self):
        return KLineToQlib._generate_5min_timestamps(DATE, 48, "5min")

    def test_count(self):
        """5min 每天 50 条（上午 25 + 下午 25）。"""
        ts = self.gen()
        assert len(ts) == 50, f"期望 50 条，实际 {len(ts)}"

    def test_contains_morning_close_1130(self):
        """含 11:30（上午收盘）—— #9 修复关键。"""
        ts = self.gen()
        assert f"{DATE} 11:30:00" in ts, "应含 11:30 上午收盘"

    def test_contains_afternoon_close_1500(self):
        """含 15:00（全天收盘）—— #9 修复关键。"""
        ts = self.gen()
        assert f"{DATE} 15:00:00" in ts, "应含 15:00 全天收盘"

    def test_first_is_0930(self):
        """首条是 09:30。"""
        ts = self.gen()
        assert ts[0] == f"{DATE} 09:30:00"

    def test_step_is_5min(self):
        """相邻时间戳步长 5 分钟（跳过午休）。"""
        ts = self.gen()

        def to_minutes(s):
            t = s.split(" ")[1]
            h, m = int(t[:2]), int(t[3:5])
            return h * 60 + m

        mins = [to_minutes(s) for s in ts]
        # 上午段步长 5
        morning = [m for m in mins if m <= 690]
        diffs = [morning[i+1] - morning[i] for i in range(len(morning)-1)]
        assert all(d == 5 for d in diffs), f"上午步长应全为5，实际 {set(diffs)}"
        # 下午段步长 5
        afternoon = [m for m in mins if m >= 780]
        diffs = [afternoon[i+1] - afternoon[i] for i in range(len(afternoon)-1)]
        assert all(d == 5 for d in diffs), f"下午步长应全为5，实际 {set(diffs)}"


class TestGenerateGenericMinTimestamps:
    """generic 函数（15min/30min/60min 用）也应含 15:00。"""

    def test_15min_contains_1500(self):
        ts = KLineToQlib._generate_generic_min_timestamps(DATE, 16, "15min")
        assert f"{DATE} 15:00:00" in ts, "15min 应含 15:00"

    def test_30min_contains_1500(self):
        ts = KLineToQlib._generate_generic_min_timestamps(DATE, 8, "30min")
        assert f"{DATE} 15:00:00" in ts, "30min 应含 15:00"

    def test_60min_contains_1500(self):
        ts = KLineToQlib._generate_generic_min_timestamps(DATE, 4, "60min")
        assert f"{DATE} 15:00:00" in ts, "60min 应含 15:00"
