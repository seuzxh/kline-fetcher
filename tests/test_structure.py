#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目结构静态测试：验证导入路径、类组织、CLI 分发、常量完整性。

无需 API 与网络，默认运行。覆盖 v2.1.0 拆分后的结构正确性。
"""
import inspect


class TestPackageStructure:
    """验证包入口与三类 fetcher 的导出。"""

    def test_package_exports(self):
        import kline_fetcher
        assert hasattr(kline_fetcher, "KLineFetcher")
        assert hasattr(kline_fetcher, "MinKLineFetcher")
        assert hasattr(kline_fetcher, "ConceptPlateFetcher")
        assert hasattr(kline_fetcher, "KLineToQlib")
        assert hasattr(kline_fetcher, "AdjustType")
        assert kline_fetcher.__version__ == "3.0.0"

    def test_all_exports(self):
        import kline_fetcher
        assert set(kline_fetcher.__all__) == {
            "KLineFetcher", "MinKLineFetcher", "ConceptPlateFetcher",
            "TrendFetcher", "KLineToQlib", "AdjustType",
        }

    def test_inheritance_chain(self):
        from kline_fetcher import KLineFetcher, MinKLineFetcher, ConceptPlateFetcher
        assert issubclass(MinKLineFetcher, KLineFetcher)
        assert issubclass(ConceptPlateFetcher, KLineFetcher)

    def test_module_all_declarations(self):
        """各模块都有 __all__。"""
        from kline_fetcher import _base, min_kline, concept_plate
        assert hasattr(_base, "__all__")
        assert hasattr(min_kline, "__all__")
        assert hasattr(concept_plate, "__all__")

    def test_backward_compat_shim(self):
        """旧导入路径 from kline_fetcher.fetcher import 仍可用。"""
        from kline_fetcher.fetcher import (
            KLineFetcher, MinKLineFetcher, ConceptPlateFetcher, AdjustType
        )
        assert KLineFetcher.__module__ == "kline_fetcher._base"


class TestMethodAttribution:
    """验证方法归属：日K在 base，分钟K在 MinKLineFetcher，概念板块在 ConceptPlateFetcher。"""

    def test_base_has_day_methods(self):
        from kline_fetcher import KLineFetcher
        for m in ["fetch_day_kline", "fetch_day_kline_with_factor",
                  "fetch_trade_calendar", "get_stock_info", "infer_market"]:
            assert hasattr(KLineFetcher, m), f"KLineFetcher 缺 {m}"

    def test_base_lacks_min_concept_methods(self):
        from kline_fetcher import KLineFetcher
        for m in ["fetch_min_kline", "get_all_concept_plates", "get_concept_plate_kline"]:
            assert not hasattr(KLineFetcher, m), f"KLineFetcher 不应有 {m}"

    def test_min_fetcher_methods(self):
        from kline_fetcher import MinKLineFetcher
        assert hasattr(MinKLineFetcher, "fetch_min_kline")
        assert not hasattr(MinKLineFetcher, "get_all_concept_plates")

    def test_concept_fetcher_methods(self):
        from kline_fetcher import ConceptPlateFetcher
        for m in ["get_all_concept_plates", "get_concept_plate_kline",
                  "get_concept_plate_stocks", "get_stock_concept_plates"]:
            assert hasattr(ConceptPlateFetcher, m)


class TestDownloadLayer:
    """验证 download.py 的导入、分发逻辑、股池完整性。"""

    def test_import_download_functions(self):
        from kline_fetcher.download import download_day_kline, download_min_kline, main
        assert callable(download_day_kline)
        assert callable(download_min_kline)
        assert callable(main)

    def test_day_download_uses_KLineFetcher(self):
        """download_day_kline 用 KLineFetcher + fetch_day_kline_with_factor。"""
        from kline_fetcher import download as dl
        src = inspect.getsource(dl.download_day_kline)
        assert "KLineFetcher()" in src
        assert "fetch_day_kline_with_factor" in src

    def test_min_download_uses_MinKLineFetcher(self):
        """download_min_kline 用 MinKLineFetcher + fetch_min_kline。"""
        from kline_fetcher import download as dl
        src = inspect.getsource(dl.download_min_kline)
        assert "MinKLineFetcher()" in src
        assert "fetch_min_kline" in src

    def test_pool_map_completeness(self):
        from kline_fetcher.download import POOL_MAP
        for pool in ["all", "csi300", "csi500", "csi800", "csi1000", "csiall"]:
            assert pool in POOL_MAP, f"缺股池: {pool}"


class TestConverterStatics:
    """验证 KLineToQlib 静态方法与常量。"""

    def test_code_to_qlib_dir(self):
        from kline_fetcher.converter import KLineToQlib
        assert KLineToQlib.code_to_qlib_dir("600519") == "sh600519"
        assert KLineToQlib.code_to_qlib_dir("SH600519") == "sh600519"
        assert KLineToQlib.code_to_qlib_dir("000001") == "sz000001"
        assert KLineToQlib.code_to_qlib_dir("sz000001") == "sz000001"
        assert KLineToQlib.code_to_qlib_dir("830799") == "bj830799"

    def test_fields_constants(self):
        from kline_fetcher.converter import QLIB_DAY_FIELDS, QLIB_MIN_FIELDS
        expected = ["open", "high", "low", "close", "volume", "factor", "vwap"]
        assert QLIB_DAY_FIELDS == expected
        assert QLIB_MIN_FIELDS == expected
