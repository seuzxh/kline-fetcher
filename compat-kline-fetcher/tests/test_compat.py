#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""兼容壳回归：全部旧导入路径可用，且与实现包指向同一对象。"""


class TestCompatShell:
    def test_root_exports_and_version(self):
        import kline_fetcher
        assert set(kline_fetcher.__all__) == {
            "KLineFetcher", "MinKLineFetcher", "ConceptPlateFetcher",
            "TrendFetcher", "KLineToQlib", "AdjustType",
        }
        assert kline_fetcher.__version__ == "3.1.0"

    def test_root_same_objects(self):
        import kline_fetcher as kf
        import tzt_api
        import kline_qlib
        assert kf.KLineFetcher is tzt_api.KLineFetcher
        assert kf.TrendFetcher is tzt_api.TrendFetcher
        assert kf.KLineToQlib is kline_qlib.KLineToQlib

    def test_fetcher_shim(self):
        from kline_fetcher.fetcher import (
            KLineFetcher, MinKLineFetcher, ConceptPlateFetcher, TrendFetcher,
            AdjustType, MARKET_CODE_MAP, PRICE_SCALE, TURNOVER_SCALE,
        )
        from tzt_api import KLineFetcher as real
        assert KLineFetcher is real

    def test_converter_shim(self):
        import kline_fetcher.converter as shim
        from kline_qlib.converter import KLineToQlib as real, QLIB_DAY_FIELDS
        assert shim.KLineToQlib is real
        assert shim.QLIB_DAY_FIELDS == QLIB_DAY_FIELDS

    def test_download_shim(self):
        import kline_fetcher.download as shim
        from kline_qlib.download import download_day_kline as real, main
        assert shim.download_day_kline is real
        assert callable(shim.main)

    def test_server_shim(self):
        from kline_fetcher.server import app, main
        from kline_qlib.server import app as real_app
        assert app is real_app
        assert callable(main)

    def test_old_semantics_unchanged(self):
        """指数优先等行为经兼容壳不变（抽样）。"""
        from kline_fetcher import KLineFetcher
        assert KLineFetcher.infer_market("000001") == 1
        assert KLineFetcher.infer_market("sz000001") == 0
        assert not KLineFetcher.is_index("sz000300")
