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

    def test_fetch_day_kline_adjust_qfq(self, day_fetcher):
        """前复权数据可获取。"""
        data = day_fetcher.fetch_day_kline(TEST_CODE, count=-3, market=TEST_MARKET, adjust="qfq")
        assert data is not None and len(data) > 0

    def test_fetch_day_kline_adjust_hfq(self, day_fetcher):
        """后复权数据可获取。"""
        data = day_fetcher.fetch_day_kline(TEST_CODE, count=-3, market=TEST_MARKET, adjust="hfq")
        assert data is not None and len(data) > 0

    def test_fetch_day_kline_adjust_none(self, day_fetcher):
        """不复权数据可获取。"""
        data = day_fetcher.fetch_day_kline(TEST_CODE, count=-3, market=TEST_MARKET, adjust="none")
        assert data is not None and len(data) > 0

    def test_hfq_price_ge_none_price(self, day_fetcher):
        """后复权价 >= 不复权价（历史分红送股使后复权价更高或相等）。"""
        hfq = day_fetcher.fetch_day_kline(TEST_CODE, count=-1, market=TEST_MARKET, adjust="hfq")
        none = day_fetcher.fetch_day_kline(TEST_CODE, count=-1, market=TEST_MARKET, adjust="none")
        if hfq and none and none[-1]["close"] > 0:
            assert hfq[-1]["close"] >= none[-1]["close"]

    def test_fetch_day_kline_invalid_code(self, day_fetcher):
        """无效股票代码应优雅返回 None，不抛异常。"""
        data = day_fetcher.fetch_day_kline("99999999", count=-3, market=TEST_MARKET, adjust="none")
        assert data is None or data == []

    def test_fetch_trade_calendar(self, day_fetcher):
        """交易日历可获取（取近一年，避免过久）。"""
        cal = day_fetcher.fetch_trade_calendar(start_year=2026, end_year=2026)
        assert cal is not None
        assert len(cal) > 0
        assert all(isinstance(d, str) for d in cal)
        assert all(len(d) == 10 for d in cal)  # yyyy-mm-dd

    def test_infer_market_all_prefixes(self):
        """infer_market 覆盖所有市场前缀。"""
        assert KLineFetcher.infer_market("SH600519") == 1
        assert KLineFetcher.infer_market("sz000001") == 0
        assert KLineFetcher.infer_market("Bj830799") == 103
        assert KLineFetcher.infer_market("688981") == 1   # 科创板
        assert KLineFetcher.infer_market("300750") == 0   # 创业板


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

    def test_fetch_min_kline_15min(self, min_fetcher):
        """15min 频率可获取。"""
        data = min_fetcher.fetch_min_kline(TEST_CODE, freq="15min", count=-5, market=TEST_MARKET)
        assert data is not None and len(data) > 0

    def test_fetch_min_kline_30min(self, min_fetcher):
        """30min 频率可获取。"""
        data = min_fetcher.fetch_min_kline(TEST_CODE, freq="30min", count=-5, market=TEST_MARKET)
        assert data is not None and len(data) > 0

    def test_fetch_min_kline_60min(self, min_fetcher):
        """60min 频率可获取。"""
        data = min_fetcher.fetch_min_kline(TEST_CODE, freq="60min", count=-5, market=TEST_MARKET)
        assert data is not None and len(data) > 0

    def test_fetch_min_kline_adjust_hfq(self, min_fetcher):
        """分钟K线支持后复权。"""
        data = min_fetcher.fetch_min_kline(TEST_CODE, freq="5min", count=-3,
                                           market=TEST_MARKET, adjust="hfq")
        assert data is not None and len(data) > 0

    def test_fetch_min_kline_invalid_freq(self, min_fetcher):
        """无效 freq 应优雅返回 None。"""
        data = min_fetcher.fetch_min_kline(TEST_CODE, freq="invalid", count=-3, market=TEST_MARKET)
        assert data is None

    def test_fetch_min_kline_invalid_code(self, min_fetcher):
        """无效股票代码应优雅返回 None 或空。"""
        data = min_fetcher.fetch_min_kline("99999999", freq="5min", count=-3, market=TEST_MARKET)
        assert data is None or len(data) == 0

    def test_fetch_min_kline_market_inference(self, min_fetcher):
        """market=None 时自动推断市场（不传 market）。"""
        data = min_fetcher.fetch_min_kline(TEST_CODE, freq="5min", count=-3)
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

    def test_get_concept_plate_stocks_pagination(self, plate_fetcher):
        """分页参数：start>0 取第二页。"""
        page1 = plate_fetcher.get_concept_plate_stocks(TEST_PLATE, start=0, count=3)
        page2 = plate_fetcher.get_concept_plate_stocks(TEST_PLATE, start=3, count=3)
        if page1 and page2:
            # 两页不应完全相同（除非成份股不足 3 只）
            codes1 = {s["code"] for s in page1}
            codes2 = {s["code"] for s in page2}
            assert codes1 != codes2 or len(page1) < 3

    def test_get_concept_plate_kline_fields(self, plate_fetcher):
        """板块K线字段完整性。"""
        data = plate_fetcher.get_concept_plate_kline(TEST_PLATE, count=-3)
        if data:
            required = ["date", "open", "high", "low", "close", "volume"]
            assert all(k in data[-1] for k in required)

    def test_get_all_concept_plates_market_value(self, plate_fetcher):
        """所有板块的 market 字段应为 44（概念板块市场）。"""
        plates = plate_fetcher.get_all_concept_plates()
        if plates:
            assert all(p.get("market") == 44 for p in plates[:10])
