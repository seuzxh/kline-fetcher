#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TrendFetcher 集成测试：验证当日/历史分时数据在真实 API 下正常工作。

需要网络与中焯行情 API。默认不运行（标记为 integration），手动触发：
    pytest tests/test_trend_integration.py -m integration

或在已配置 KLINE_API_BASE_URL 的环境里：
    pytest tests/test_trend_integration.py -m integration --override-ini="addopts=-m integration"
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

from kline_fetcher import TrendFetcher

TEST_CODE = "600519"    # 贵州茅台
TEST_MARKET = 1         # 上海
TEST_HISTORY_DATE = "20260611"  # 历史日期


@pytest.fixture(scope="module")
def trend_fetcher():
    return TrendFetcher()


# ============ 1. 当日分时数据 ============

class TestIntradayTrend:
    def test_fetch_intraday_returns_dict(self, trend_fetcher):
        data = trend_fetcher.fetch_intraday_trend(TEST_CODE, market=TEST_MARKET)
        assert data is not None
        assert isinstance(data, dict)

    def test_intraday_has_market_date(self, trend_fetcher):
        data = trend_fetcher.fetch_intraday_trend(TEST_CODE, market=TEST_MARKET)
        assert data and "market_date" in data
        assert data["market_date"]  # 非空

    def test_intraday_has_pre_market_key(self, trend_fetcher):
        data = trend_fetcher.fetch_intraday_trend(TEST_CODE, market=TEST_MARKET)
        assert data and "pre_market" in data
        assert isinstance(data["pre_market"], list)

    def test_intraday_has_trading_key(self, trend_fetcher):
        data = trend_fetcher.fetch_intraday_trend(TEST_CODE, market=TEST_MARKET)
        assert data and "trading" in data
        assert isinstance(data["trading"], list)

    def test_intraday_trading_not_empty(self, trend_fetcher):
        """当日盘中数据应有内容（交易日测试时）。"""
        data = trend_fetcher.fetch_intraday_trend(TEST_CODE, market=TEST_MARKET)
        assert data and len(data["trading"]) > 0

    def test_intraday_pre_market_fields(self, trend_fetcher):
        """盘前集合竞价字段完整性。"""
        data = trend_fetcher.fetch_intraday_trend(TEST_CODE, market=TEST_MARKET)
        if data and data["pre_market"]:
            required = ["date", "time", "ref_price", "matched_vol",
                        "non_matched_vol_buy", "non_matched_vol_sell", "phase"]
            item = data["pre_market"][0]
            assert all(k in item for k in required)
            assert item["phase"] == "pre-market"

    def test_intraday_trading_fields(self, trend_fetcher):
        """盘中数据字段完整性。"""
        data = trend_fetcher.fetch_intraday_trend(TEST_CODE, market=TEST_MARKET)
        if data and data["trading"]:
            required = ["date", "time", "last_price", "avg_price",
                        "volume", "turnover", "phase"]
            item = data["trading"][0]
            assert all(k in item for k in required)
            assert item["phase"] == "trading"

    def test_intraday_trading_time_range(self, trend_fetcher):
        """盘中数据时间应在 09:30-15:00 之间。"""
        data = trend_fetcher.fetch_intraday_trend(TEST_CODE, market=TEST_MARKET)
        if data and data["trading"]:
            first_time = data["trading"][0]["time"]
            assert first_time >= "09:30:00"
            last_time = data["trading"][-1]["time"]
            assert last_time <= "15:00:00"

    def test_intraday_pre_market_time_range(self, trend_fetcher):
        """盘前数据时间应在 09:15-09:25 之间。"""
        data = trend_fetcher.fetch_intraday_trend(TEST_CODE, market=TEST_MARKET)
        if data and data["pre_market"]:
            first_time = data["pre_market"][0]["time"]
            assert first_time >= "09:15:00"
            last_time = data["pre_market"][-1]["time"]
            assert last_time <= "09:25:00"

    def test_intraday_market_inference(self, trend_fetcher):
        """market=None 时自动推断市场。"""
        data = trend_fetcher.fetch_intraday_trend(TEST_CODE)
        assert data is not None

    def test_intraday_code_prefix(self, trend_fetcher):
        """支持 SH 前缀代码。"""
        data = trend_fetcher.fetch_intraday_trend("SH600519")
        assert data is not None

    def test_intraday_price_reasonable(self, trend_fetcher):
        """盘中价格应为合理正值（非零）。"""
        data = trend_fetcher.fetch_intraday_trend(TEST_CODE, market=TEST_MARKET)
        if data and data["trading"]:
            for item in data["trading"]:
                assert item["last_price"] > 0

    def test_intraday_volume_non_negative(self, trend_fetcher):
        """成交量应为非负数。"""
        data = trend_fetcher.fetch_intraday_trend(TEST_CODE, market=TEST_MARKET)
        if data and data["trading"]:
            for item in data["trading"]:
                assert item["volume"] >= 0


# ============ 2. 历史分时数据 ============

class TestHistoryTrend:
    def test_fetch_history_returns_dict(self, trend_fetcher):
        data = trend_fetcher.fetch_history_trend(TEST_CODE, TEST_HISTORY_DATE, market=TEST_MARKET)
        assert data is not None
        assert isinstance(data, dict)

    def test_history_has_market_date(self, trend_fetcher):
        data = trend_fetcher.fetch_history_trend(TEST_CODE, TEST_HISTORY_DATE, market=TEST_MARKET)
        assert data and "market_date" in data

    def test_history_trading_not_empty(self, trend_fetcher):
        data = trend_fetcher.fetch_history_trend(TEST_CODE, TEST_HISTORY_DATE, market=TEST_MARKET)
        assert data and len(data["trading"]) > 0

    def test_history_trading_date_matches(self, trend_fetcher):
        """历史分时数据的 date 字段应与请求日期一致。"""
        data = trend_fetcher.fetch_history_trend(TEST_CODE, TEST_HISTORY_DATE, market=TEST_MARKET)
        if data and data["trading"]:
            expected = f"{TEST_HISTORY_DATE[0:4]}-{TEST_HISTORY_DATE[4:6]}-{TEST_HISTORY_DATE[6:8]}"
            assert data["trading"][0]["date"] == expected

    def test_history_trading_fields(self, trend_fetcher):
        """历史分时盘中字段完整性。"""
        data = trend_fetcher.fetch_history_trend(TEST_CODE, TEST_HISTORY_DATE, market=TEST_MARKET)
        if data and data["trading"]:
            required = ["date", "time", "last_price", "avg_price",
                        "volume", "turnover", "phase"]
            item = data["trading"][0]
            assert all(k in item for k in required)

    def test_history_market_inference(self, trend_fetcher):
        """market=None 时自动推断市场。"""
        data = trend_fetcher.fetch_history_trend(TEST_CODE, TEST_HISTORY_DATE)
        assert data is not None

    def test_history_invalid_date(self, trend_fetcher):
        """无效日期格式应返回 None。"""
        data = trend_fetcher.fetch_history_trend(TEST_CODE, "invalid", market=TEST_MARKET)
        assert data is None

    def test_history_trading_count_241(self, trend_fetcher):
        """A 股盘中分时标准为 241 条（09:30-15:00 每分钟一条）。"""
        data = trend_fetcher.fetch_history_trend(TEST_CODE, TEST_HISTORY_DATE, market=TEST_MARKET)
        if data and data["trading"]:
            assert len(data["trading"]) == 241


# ============ 3. fetch_trend 自动路由 ============

class TestFetchTrendAutoRoute:
    def test_fetch_trend_none_date(self, trend_fetcher):
        """date=None 时应获取当日数据。"""
        data = trend_fetcher.fetch_trend(TEST_CODE, market=TEST_MARKET)
        assert data is not None

    def test_fetch_trend_zero_date(self, trend_fetcher):
        """date='0' 时应获取当日数据。"""
        data = trend_fetcher.fetch_trend(TEST_CODE, date="0", market=TEST_MARKET)
        assert data is not None

    def test_fetch_trend_history_date(self, trend_fetcher):
        """date=YYYYMMDD 时应获取历史数据。"""
        data = trend_fetcher.fetch_trend(TEST_CODE, date=TEST_HISTORY_DATE, market=TEST_MARKET)
        assert data is not None


# ============ 4. 继承关系验证 ============

class TestInheritance:
    def test_inherited_day_kline(self, trend_fetcher):
        """TrendFetcher 继承基类的日K方法。"""
        data = trend_fetcher.fetch_day_kline(TEST_CODE, count=-1, market=TEST_MARKET, adjust="none")
        assert data is not None and len(data) > 0

    def test_inherited_infer_market(self):
        """TrendFetcher 继承 infer_market 静态方法。"""
        assert TrendFetcher.infer_market("600519") == 1
        assert TrendFetcher.infer_market("000001") == 0
