#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""拆分后接口集成测试：验证 KLineFetcher / MinKLineFetcher / ConceptPlateFetcher
的各类方法在真实 API 下正常工作。

需要网络与中焯行情 API。默认不运行（标记为 integration），手动触发：
    pytest tests/test_split_interfaces.py -m integration

或在已配置 KLINE_API_BASE_URL 的环境里：
    pytest tests/test_split_interfaces.py -m integration --override-ini="addopts=-m integration"
"""
import os

import pytest

# 若未配置 API 地址，跳过全部（避免 CI/无网络环境报错）
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("KLINE_API_BASE_URL"),
        reason="需要设置 KLINE_API_BASE_URL 环境变量才能运行集成测试",
    ),
]

from kline_fetcher import KLineFetcher, MinKLineFetcher, ConceptPlateFetcher

TEST_CODE = "600519"    # 贵州茅台
TEST_MARKET = 1         # 上海
TEST_PLATE = "994612"   # 概念板块


@pytest.fixture(scope="module")
def day_fetcher():
    return KLineFetcher()


@pytest.fixture(scope="module")
def min_fetcher():
    return MinKLineFetcher()


@pytest.fixture(scope="module")
def plate_fetcher():
    return ConceptPlateFetcher()


# ============ 1. KLineFetcher（base，日K）============

class TestKLineFetcherDay:
    def test_fetch_day_kline_by_count(self, day_fetcher):
        data = day_fetcher.fetch_day_kline(TEST_CODE, count=-3, market=TEST_MARKET, adjust="none")
        assert data is not None and len(data) > 0

    def test_day_kline_has_no_time_field(self, day_fetcher):
        data = day_fetcher.fetch_day_kline(TEST_CODE, count=-1, market=TEST_MARKET, adjust="none")
        assert data and "time" not in data[-1]

    def test_day_kline_field_completeness(self, day_fetcher):
        data = day_fetcher.fetch_day_kline(TEST_CODE, count=-1, market=TEST_MARKET, adjust="none")
        required = ["date", "open", "high", "low", "close", "volume", "amount"]
        assert data and all(k in data[-1] for k in required)

    def test_fetch_day_kline_by_date_range(self, day_fetcher):
        data = day_fetcher.fetch_day_kline(TEST_CODE, market=TEST_MARKET,
                                           begindate="20260601", enddate="20260610", adjust="none")
        assert data is not None and len(data) > 0

    def test_fetch_day_kline_with_factor(self, day_fetcher):
        data = day_fetcher.fetch_day_kline_with_factor(TEST_CODE, count=-3, market=TEST_MARKET)
        assert data and "factor" in data[-1]
        assert data[-1]["factor"] > 1  # 后复权/不复权比值

    def test_get_stock_info(self, day_fetcher):
        info = day_fetcher.get_stock_info(TEST_CODE, market=TEST_MARKET)
        assert info is not None and info.get("code") is not None

    def test_infer_market_static(self):
        assert KLineFetcher.infer_market("600519") == 1
        assert KLineFetcher.infer_market("000001") == 0


# ============ 2. MinKLineFetcher（分钟K）============

class TestMinKLineFetcher:
    def test_fetch_min_kline_5min(self, min_fetcher):
        data = min_fetcher.fetch_min_kline(TEST_CODE, freq="5min", count=-10, market=TEST_MARKET)
        assert data is not None and len(data) > 0

    def test_min_kline_has_time_field(self, min_fetcher):
        data = min_fetcher.fetch_min_kline(TEST_CODE, freq="5min", count=-3, market=TEST_MARKET)
        assert data and "time" in data[-1]

    def test_fetch_min_kline_1min(self, min_fetcher):
        data = min_fetcher.fetch_min_kline(TEST_CODE, freq="1min", count=-5, market=TEST_MARKET)
        assert data is not None and len(data) > 0

    def test_fetch_min_kline_pagination(self, min_fetcher):
        data = min_fetcher.fetch_min_kline(TEST_CODE, freq="5min", count=-10,
                                           market=TEST_MARKET, pages=2)
        assert data is not None  # 翻页去重后可能少于 2*10

    def test_inherited_day_kline(self, min_fetcher):
        """MinKLineFetcher 继承基类的日K方法。"""
        data = min_fetcher.fetch_day_kline(TEST_CODE, count=-1, market=TEST_MARKET, adjust="none")
        assert data is not None and len(data) > 0


# ============ 3. ConceptPlateFetcher（概念板块）============

class TestConceptPlateFetcher:
    def test_get_all_concept_plates(self, plate_fetcher):
        plates = plate_fetcher.get_all_concept_plates()
        assert plates is not None and len(plates) > 0

    def test_plate_field_completeness(self, plate_fetcher):
        plates = plate_fetcher.get_all_concept_plates()
        assert plates and all(k in plates[0] for k in ["code", "name", "market"])

    def test_get_concept_plate_kline(self, plate_fetcher):
        data = plate_fetcher.get_concept_plate_kline(TEST_PLATE, count=-5)
        assert data is not None and len(data) > 0

    def test_get_concept_plate_stocks(self, plate_fetcher):
        stocks = plate_fetcher.get_concept_plate_stocks(TEST_PLATE, start=0, count=5)
        assert stocks is not None and len(stocks) > 0

    def test_stock_field_completeness(self, plate_fetcher):
        stocks = plate_fetcher.get_concept_plate_stocks(TEST_PLATE, start=0, count=3)
        assert stocks and all(k in stocks[0] for k in ["code", "name", "market"])

    def test_get_stock_concept_plates(self, plate_fetcher):
        plates = plate_fetcher.get_stock_concept_plates(TEST_CODE, TEST_MARKET)
        assert plates is not None  # 可能为空列表（取决于股票是否属于概念板块）

    def test_inherited_day_kline(self, plate_fetcher):
        """ConceptPlateFetcher 继承基类的日K方法。"""
        data = plate_fetcher.fetch_day_kline(TEST_CODE, count=-1, market=TEST_MARKET, adjust="none")
        assert data is not None and len(data) > 0
