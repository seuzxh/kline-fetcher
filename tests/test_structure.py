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
        assert kline_fetcher.__version__ == "3.0.1"

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
        # 指数优先：裸码 000001 按上证指数 → sh；显式前缀 → 按前缀
        assert KLineToQlib.code_to_qlib_dir("000001") == "sh000001"
        assert KLineToQlib.code_to_qlib_dir("sz000001") == "sz000001"
        assert KLineToQlib.code_to_qlib_dir("830799") == "bj830799"

    def test_code_to_qlib_dir_indices(self):
        """指数优先：白名单指数按其所属市场命名目录。"""
        from kline_fetcher.converter import KLineToQlib
        assert KLineToQlib.code_to_qlib_dir("000300") == "sh000300"
        assert KLineToQlib.code_to_qlib_dir("sh000300") == "sh000300"
        assert KLineToQlib.code_to_qlib_dir("000852") == "sh000852"
        assert KLineToQlib.code_to_qlib_dir("399001") == "sz399001"
        assert KLineToQlib.code_to_qlib_dir("399006") == "sz399006"
        assert KLineToQlib.code_to_qlib_dir("399999") == "sz399999"  # 399 前缀规则
        assert KLineToQlib.code_to_qlib_dir("899050") == "bj899050"  # 北证50
        # 深市个股仍正确（不与指数白名单冲突的代码）
        assert KLineToQlib.code_to_qlib_dir("000002") == "sz000002"

    def test_fields_constants(self):
        from kline_fetcher.converter import QLIB_DAY_FIELDS, QLIB_MIN_FIELDS
        expected = ["open", "high", "low", "close", "volume", "factor", "vwap"]
        assert QLIB_DAY_FIELDS == expected
        assert QLIB_MIN_FIELDS == expected


class TestIndexDetection:
    """指数优先判断：is_index / get_index_info / infer_market。"""

    def test_is_index_whitelist(self):
        from kline_fetcher import KLineFetcher
        for code in ["000001", "000300", "000688", "000852", "000905", "000906", "000016"]:
            assert KLineFetcher.is_index(code), f"{code} 应为指数"
        for code in ["399001", "399006", "399102"]:  # 399 前缀规则
            assert KLineFetcher.is_index(code), f"{code} 应为指数"

    def test_is_index_stocks(self):
        from kline_fetcher import KLineFetcher
        for code in ["600519", "000002", "300750", "830799", "688981"]:
            assert not KLineFetcher.is_index(code), f"{code} 应为个股"

    def test_is_index_explicit_prefix_wins(self):
        """显式 sz 前缀优先于指数白名单（sz000001 = 平安银行）。"""
        from kline_fetcher import KLineFetcher
        assert not KLineFetcher.is_index("sz000001")
        assert not KLineFetcher.is_index("SZ000300")
        assert KLineFetcher.is_index("sh000300")  # sh 前缀与指数市场一致

    def test_get_index_info(self):
        from kline_fetcher import KLineFetcher
        assert KLineFetcher.get_index_info("000300") == ("沪深300", 1)
        assert KLineFetcher.get_index_info("sh000300") == ("沪深300", 1)
        assert KLineFetcher.get_index_info("399006") == ("创业板指", 0)
        assert KLineFetcher.get_index_info("600519") is None
        assert KLineFetcher.get_index_info("sz000001") is None  # 显式个股

    def test_infer_market_index_priority(self):
        """infer_market 指数优先：白名单指数按其市场。"""
        from kline_fetcher import KLineFetcher
        assert KLineFetcher.infer_market("000300") == 1   # 沪深300 → 沪
        assert KLineFetcher.infer_market("000001") == 1   # 上证指数（指数优先）
        assert KLineFetcher.infer_market("000852") == 1   # 中证1000 → 沪
        assert KLineFetcher.infer_market("399006") == 0   # 创业板指 → 深
        assert KLineFetcher.infer_market("399001") == 0   # 深证成指 → 深

    def test_infer_market_stocks_unchanged(self):
        """个股推断规则不受影响。"""
        from kline_fetcher import KLineFetcher
        assert KLineFetcher.infer_market("600519") == 1
        assert KLineFetcher.infer_market("000002") == 0   # 深市个股（非白名单）
        assert KLineFetcher.infer_market("300750") == 0
        assert KLineFetcher.infer_market("sz000001") == 0  # 显式前缀 → 平安银行
        assert KLineFetcher.infer_market("830799") == 103
