#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""指数行情集成测试：验证 INDEX_CODE_MAP 全部指数可获取（防回归）。

需要网络与中焯行情 API。默认不运行（integration marker），手动触发：
    KLINE_API_BASE_URL=... pytest tests/test_indices_integration.py -m integration
"""
import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("KLINE_API_BASE_URL"),
        reason="需要设置 KLINE_API_BASE_URL 环境变量才能运行集成测试",
    ),
]

from tzt_api import KLineFetcher, MinKLineFetcher, TrendFetcher
from tzt_api.market import INDEX_CODE_MAP

# 历史分时用最近已知的交易日（周五）；当前日期附近取一个肯定的历史交易日
HISTORY_TREND_DATE = "20260821"


@pytest.fixture(scope="module")
def day_fetcher():
    return KLineFetcher()


@pytest.fixture(scope="module")
def min_fetcher():
    return MinKLineFetcher()


@pytest.fixture(scope="module")
def trend_fetcher():
    return TrendFetcher()


class TestIndexDayKline:
    """全部白名单指数的日K线（裸码，不传 market，验证指数优先推断）。"""

    @pytest.mark.parametrize("code", sorted(INDEX_CODE_MAP.keys()),
                             ids=[INDEX_CODE_MAP[c][0] for c in sorted(INDEX_CODE_MAP.keys())])
    def test_day_kline_bare_code(self, day_fetcher, code):
        """裸码不传 market → 按指数所属市场推断并返回数据。"""
        data = day_fetcher.fetch_day_kline(code, count=-1, adjust="none")
        assert data is not None and len(data) > 0, f"{code} {INDEX_CODE_MAP[code][0]} 日K线无数据"


class TestIndexMarketInference:
    def test_infer_market_matches_map(self):
        """全部白名单指数：infer_market 与 INDEX_CODE_MAP 声明的市场一致。"""
        from tzt_api import KLineFetcher
        for code, (_, market) in INDEX_CODE_MAP.items():
            assert KLineFetcher.infer_market(code) == market, f"{code} 市场推断不符"



class TestIndexOtherData:
    """代表性指数的分钟K / 当日分时 / 历史分时。"""

    def test_min_kline_sh300(self, min_fetcher):
        data = min_fetcher.fetch_min_kline("000300", freq="5min", count=-3)
        assert data is not None and len(data) > 0

    def test_min_kline_cyb(self, min_fetcher):
        data = min_fetcher.fetch_min_kline("399006", freq="1min", count=-3)
        assert data is not None and len(data) > 0

    def test_intraday_trend_csi1000(self, trend_fetcher):
        t = trend_fetcher.fetch_intraday_trend("000852")
        assert t is not None and t.get("trading")

    def test_intraday_trend_bj50(self, trend_fetcher):
        t = trend_fetcher.fetch_intraday_trend("899050")
        assert t is not None and t.get("trading")

    def test_history_trend_sh_index(self, trend_fetcher):
        t = trend_fetcher.fetch_history_trend("000001", date=HISTORY_TREND_DATE)
        assert t is not None and t.get("trading")


class TestAmbiguityRules:
    """歧义代码解析规则（真实 API 双向验证）。"""

    def test_bare_000001_is_sh_index(self, day_fetcher):
        """裸码 000001 → 上证指数（指数优先）。"""
        data = day_fetcher.fetch_day_kline("000001", count=-1, adjust="none")
        assert data is not None
        # 上证指数点位在千级以上；深市同名个股（平安银行）股价为个位数~十几元
        assert data[-1]["close"] > 1000

    def test_sz_prefix_000001_is_stock(self, day_fetcher):
        """sz000001 → 平安银行（显式前缀优先）。"""
        data = day_fetcher.fetch_day_kline("sz000001", count=-1, adjust="none")
        assert data is not None
        assert data[-1]["close"] < 100
