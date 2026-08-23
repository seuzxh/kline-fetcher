#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kline-qlib 包结构静态测试。"""
import inspect


class TestKlineQlibStructure:
    def test_exports(self):
        import kline_qlib
        assert "KLineToQlib" in kline_qlib.__all__
        assert "download_day_kline" in kline_qlib.__all__
        assert kline_qlib.__version__ == "1.0.0"

    def test_download_uses_fetchers(self):
        from kline_qlib import download as dl
        src = inspect.getsource(dl.download_day_kline)
        assert "KLineFetcher()" in src
        assert "fetch_day_kline_with_factor" in src
        src_min = inspect.getsource(dl.download_min_kline)
        assert "MinKLineFetcher()" in src_min
        assert "fetch_min_kline" in src_min

    def test_pool_map_completeness(self):
        from kline_qlib.download import POOL_MAP
        for pool in ["all", "csi300", "csi500", "csi800", "csi1000", "csiall"]:
            assert pool in POOL_MAP, f"缺股池: {pool}"

    def test_code_to_qlib_dir(self):
        from kline_qlib.converter import KLineToQlib
        assert KLineToQlib.code_to_qlib_dir("600519") == "sh600519"
        assert KLineToQlib.code_to_qlib_dir("SH600519") == "sh600519"
        assert KLineToQlib.code_to_qlib_dir("000001") == "sh000001"    # 指数优先
        assert KLineToQlib.code_to_qlib_dir("sz000001") == "sz000001"  # 显式前缀
        assert KLineToQlib.code_to_qlib_dir("000300") == "sh000300"
        assert KLineToQlib.code_to_qlib_dir("399999") == "sz399999"
        assert KLineToQlib.code_to_qlib_dir("899050") == "bj899050"
        assert KLineToQlib.code_to_qlib_dir("000002") == "sz000002"

    def test_fields_constants(self):
        from kline_qlib.converter import QLIB_DAY_FIELDS, QLIB_MIN_FIELDS
        expected = ["open", "high", "low", "close", "volume", "factor", "vwap"]
        assert QLIB_DAY_FIELDS == expected
        assert QLIB_MIN_FIELDS == expected
