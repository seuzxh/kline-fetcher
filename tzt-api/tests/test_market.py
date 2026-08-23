#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tzt_api.market 单一事实源测试（纯函数，不依赖 numpy/qlib 侧）。"""
from tzt_api.market import (
    MARKET_CODE_MAP,
    MARKET_TO_PREFIX,
    INDEX_CODE_MAP,
    INDEX_CODE_PREFIXES,
    numeric_code,
    is_index,
    get_index_info,
    infer_market,
)


class TestMarketTables:
    def test_market_code_map(self):
        assert MARKET_CODE_MAP == {"sh": 1, "sz": 0, "bj": 103}

    def test_market_to_prefix_is_reverse(self):
        for prefix, code in MARKET_CODE_MAP.items():
            assert MARKET_TO_PREFIX[code] == prefix

    def test_index_code_map_entries(self):
        assert INDEX_CODE_MAP["000300"] == ("沪深300", 1)
        assert INDEX_CODE_MAP["399006"] == ("创业板指", 0)
        assert INDEX_CODE_MAP["899050"] == ("北证50", 103)
        assert len(INDEX_CODE_MAP) == 26
        assert INDEX_CODE_PREFIXES == ("399",)


class TestNumericCode:
    def test_strips_prefix(self):
        assert numeric_code("sh600519") == "600519"
        assert numeric_code("SZ000001") == "000001"
        assert numeric_code("bj830799") == "830799"

    def test_no_prefix_unchanged(self):
        assert numeric_code("600519") == "600519"


class TestIsIndex:
    def test_whitelist_and_prefix(self):
        for code in ["000001", "000300", "000688", "000852", "000905", "399001", "399006", "399999"]:
            assert is_index(code), f"{code} 应为指数"

    def test_stocks_not_index(self):
        for code in ["600519", "000002", "300750", "830799", "688981"]:
            assert not is_index(code), f"{code} 应为个股"

    def test_explicit_sz_bj_prefix_wins(self):
        assert not is_index("sz000001")
        assert not is_index("SZ000300")
        assert is_index("sh000300")


class TestInferMarket:
    def test_index_priority(self):
        assert infer_market("000001") == 1   # 上证指数（指数优先）
        assert infer_market("000300") == 1
        assert infer_market("399006") == 0
        assert infer_market("399999") == 0

    def test_stocks(self):
        assert infer_market("600519") == 1
        assert infer_market("000002") == 0
        assert infer_market("300750") == 0
        assert infer_market("sz000001") == 0
        assert infer_market("830799") == 103

    def test_get_index_info(self):
        assert get_index_info("000300") == ("沪深300", 1)
        assert get_index_info("399006") == ("创业板指", 0)
        assert get_index_info("600519") is None
        assert get_index_info("sz000001") is None


class TestFetcherDelegation:
    """KLineFetcher 静态方法委托 market 后行为不变。"""

    SAMPLES = ["600519", "SH600519", "sz000001", "000001", "000300",
               "399006", "399999", "830799", "000002", "899050"]

    def test_matches_kline_fetcher_statics(self):
        from tzt_api import KLineFetcher

        for c in self.SAMPLES:
            assert KLineFetcher.infer_market(c) == infer_market(c), c
            assert KLineFetcher.is_index(c) == is_index(c), c
