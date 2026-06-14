#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TrendFetcher 单元测试：验证内部方法、参数构造、路由逻辑。

无需网络与 API，默认运行：
    pytest tests/test_trend_unit.py
"""
import pytest

from kline_fetcher import TrendFetcher
from kline_fetcher._base import PRICE_SCALE, TURNOVER_SCALE


@pytest.fixture(scope="module")
def fetcher():
    return TrendFetcher()


# ============ 1. _convert_trend_time 时间转换 ============

class TestConvertTrendTime:
    def test_normal_timestamp(self, fetcher):
        dt = fetcher._convert_trend_time(20260612093000)
        assert dt["date"] == "2026-06-12"
        assert dt["time"] == "09:30:00"

    def test_premarket_timestamp(self, fetcher):
        dt = fetcher._convert_trend_time(20260612091500)
        assert dt["date"] == "2026-06-12"
        assert dt["time"] == "09:15:00"

    def test_short_timestamp_padded(self, fetcher):
        # 不足 14 位应左填充零
        dt = fetcher._convert_trend_time(93000)
        assert dt["date"] != ""
        assert dt["time"] != ""

    def test_zero_timestamp(self, fetcher):
        dt = fetcher._convert_trend_time(0)
        # zfill(14) 后全零，date/time 仍可解析但值为 0000-00-00
        assert dt["date"] == "0000-00-00"
        assert dt["time"] == "00:00:00"

    def test_invalid_timestamp_returns_empty(self, fetcher):
        # 超过 14 位无法 zfill 到正好 14
        dt = fetcher._convert_trend_time(123456789012345)
        assert dt["date"] == ""
        assert dt["time"] == ""


# ============ 2. _build_trend_params 参数构造 ============

class TestBuildTrendParams:
    def test_intraday_params(self, fetcher):
        params = fetcher._build_trend_params("600519", date=0, daycount=0)
        assert params["Action"] == 10001
        assert params["code"] == "600519"
        assert params["market"] == 1  # 上交所
        assert params["trendtypes"] == -1
        assert params["date"] == 0
        assert params["daycount"] == 0

    def test_history_params(self, fetcher):
        params = fetcher._build_trend_params("600519", date=20260611, daycount=1)
        assert params["date"] == 20260611
        assert params["daycount"] == 1

    def test_421_422_423_params_intraday(self, fetcher):
        params = fetcher._build_trend_params("600519", date=0, daycount=0)
        assert params["421.date"] == 0
        assert params["421.daycount"] == 0
        assert params["422.date"] == 0
        assert params["422.daycount"] == 0
        assert params["423.date"] == 0
        assert params["423.daycount"] == 0

    def test_421_422_423_params_history(self, fetcher):
        params = fetcher._build_trend_params("600519", date=20260611, daycount=1)
        assert params["421.date"] == 20260611
        assert params["421.daycount"] == 1
        assert params["422.date"] == 20260611
        assert params["422.daycount"] == 1
        assert params["423.date"] == 20260611
        assert params["423.daycount"] == 1

    def test_market_inference_sh(self, fetcher):
        params = fetcher._build_trend_params("600519", date=0, daycount=0)
        assert params["market"] == 1

    def test_market_inference_sz(self, fetcher):
        params = fetcher._build_trend_params("000001", date=0, daycount=0)
        assert params["market"] == 0

    def test_market_inference_bj(self, fetcher):
        params = fetcher._build_trend_params("830799", date=0, daycount=0)
        assert params["market"] == 103

    def test_market_explicit_override(self, fetcher):
        params = fetcher._build_trend_params("600519", date=0, daycount=0, market=0)
        assert params["market"] == 0

    def test_code_prefix_stripped(self, fetcher):
        params = fetcher._build_trend_params("SH600519", date=0, daycount=0)
        assert params["code"] == "600519"


# ============ 3. _parse_call_trend 盘前数据解析 ============

class TestParseCallTrend:
    def test_normal_parse(self, fetcher):
        raw = [{
            "Time": 20260612092500,
            "RefPrice": 19270000,
            "MatchedVol": 639300,
            "NonMatchedVolBuy": 3800,
            "NonMatchedVolSell": 0,
        }]
        result = fetcher._parse_call_trend(raw)
        assert len(result) == 1
        item = result[0]
        assert item["date"] == "2026-06-12"
        assert item["time"] == "09:25:00"
        assert item["ref_price"] == round(19270000 / PRICE_SCALE, 4)
        assert item["matched_vol"] == 639300
        assert item["non_matched_vol_buy"] == 3800
        assert item["non_matched_vol_sell"] == 0
        assert item["phase"] == "pre-market"

    def test_empty_list(self, fetcher):
        assert fetcher._parse_call_trend([]) == []

    def test_skip_non_dict(self, fetcher):
        raw = ["invalid", None, 123]
        assert fetcher._parse_call_trend(raw) == []

    def test_skip_invalid_time(self, fetcher):
        raw = [{"Time": 123456789012345, "RefPrice": 10000000}]  # 超 14 位
        assert fetcher._parse_call_trend(raw) == []

    def test_missing_fields_default_zero(self, fetcher):
        raw = [{"Time": 20260612091500}]  # 缺少其他字段
        result = fetcher._parse_call_trend(raw)
        assert len(result) == 1
        assert result[0]["ref_price"] == 0.0
        assert result[0]["matched_vol"] == 0.0

    def test_price_unit_conversion(self, fetcher):
        """RefPrice 原始单位万分之一元，÷1e6 → 元。"""
        raw = [{"Time": 20260612092500, "RefPrice": 19270000}]
        result = fetcher._parse_call_trend(raw)
        assert result[0]["ref_price"] == pytest.approx(19.27)


# ============ 4. _parse_trend_op 盘中数据解析 ============

class TestParseTrendOp:
    def test_normal_parse(self, fetcher):
        raw = [{
            "Time": 20260612093000,
            "LastPrice": 19270000,
            "AvgPrice": 19270008,
            "Volume": 639300,
            "Turnover": 12301000000,
        }]
        result = fetcher._parse_trend_op(raw)
        assert len(result) == 1
        item = result[0]
        assert item["date"] == "2026-06-12"
        assert item["time"] == "09:30:00"
        assert item["last_price"] == round(19270000 / PRICE_SCALE, 4)
        assert item["avg_price"] == round(19270008 / PRICE_SCALE, 4)
        assert item["volume"] == 639300
        assert item["turnover"] == round(12301000000 / TURNOVER_SCALE, 2)
        assert item["phase"] == "trading"

    def test_empty_list(self, fetcher):
        assert fetcher._parse_trend_op([]) == []

    def test_skip_non_dict(self, fetcher):
        raw = ["invalid", None]
        assert fetcher._parse_trend_op(raw) == []

    def test_skip_invalid_time(self, fetcher):
        raw = [{"Time": 123456789012345, "LastPrice": 10000000}]  # 超 14 位
        assert fetcher._parse_trend_op(raw) == []

    def test_missing_fields_default_zero(self, fetcher):
        raw = [{"Time": 20260612093000}]
        result = fetcher._parse_trend_op(raw)
        assert len(result) == 1
        assert result[0]["last_price"] == 0.0
        assert result[0]["volume"] == 0.0

    def test_price_unit_conversion(self, fetcher):
        """LastPrice/AvgPrice 原始单位万分之一元，÷1e6 → 元。"""
        raw = [{"Time": 20260612093000, "LastPrice": 19270000}]
        result = fetcher._parse_trend_op(raw)
        assert result[0]["last_price"] == pytest.approx(19.27)

    def test_turnover_unit_conversion(self, fetcher):
        """Turnover 原始单位万元，÷1e4 → 元。"""
        raw = [{"Time": 20260612093000, "Turnover": 1230100}]  # 123.01 万元
        result = fetcher._parse_trend_op(raw)
        assert result[0]["turnover"] == pytest.approx(123.01)


# ============ 5. fetch_trend 路由逻辑 ============

class TestFetchTrendRouting:
    def test_date_none_routes_to_intraday(self, fetcher, monkeypatch):
        called = {}

        def mock_intraday(code, market=None):
            called["intraday"] = (code, market)
            return {"market_date": "", "pre_market": [], "trading": []}

        def mock_history(code, date, market=None):
            called["history"] = (code, date, market)
            return None

        monkeypatch.setattr(fetcher, "fetch_intraday_trend", mock_intraday)
        monkeypatch.setattr(fetcher, "fetch_history_trend", mock_history)

        fetcher.fetch_trend("600519")
        assert "intraday" in called
        assert "history" not in called

    def test_date_zero_routes_to_intraday(self, fetcher, monkeypatch):
        called = {}

        def mock_intraday(code, market=None):
            called["intraday"] = True
            return {"market_date": "", "pre_market": [], "trading": []}

        def mock_history(code, date, market=None):
            called["history"] = True
            return None

        monkeypatch.setattr(fetcher, "fetch_intraday_trend", mock_intraday)
        monkeypatch.setattr(fetcher, "fetch_history_trend", mock_history)

        fetcher.fetch_trend("600519", date="0")
        assert "intraday" in called
        assert "history" not in called

    def test_date_specified_routes_to_history(self, fetcher, monkeypatch):
        called = {}

        def mock_intraday(code, market=None):
            called["intraday"] = True
            return None

        def mock_history(code, date, market=None):
            called["history"] = (code, date, market)
            return {"market_date": "", "pre_market": [], "trading": []}

        monkeypatch.setattr(fetcher, "fetch_intraday_trend", mock_intraday)
        monkeypatch.setattr(fetcher, "fetch_history_trend", mock_history)

        fetcher.fetch_trend("600519", date="20260611")
        assert "history" in called
        assert called["history"] == ("600519", "20260611", None)
        assert "intraday" not in called


# ============ 6. fetch_history_trend 无效日期处理 ============

class TestFetchHistoryTrendInvalidDate:
    def test_invalid_date_string(self, fetcher):
        result = fetcher.fetch_history_trend("600519", "invalid")
        assert result is None

    def test_none_date(self, fetcher):
        result = fetcher.fetch_history_trend("600519", None)
        assert result is None


# ============ 7. 继承关系验证 ============

class TestInheritance:
    def test_inherits_from_kline_fetcher(self):
        from kline_fetcher._base import KLineFetcher
        assert issubclass(TrendFetcher, KLineFetcher)

    def test_inherits_day_kline_method(self, fetcher):
        """TrendFetcher 继承基类的日K方法。"""
        assert hasattr(fetcher, "fetch_day_kline")

    def test_inherits_infer_market(self, fetcher):
        """TrendFetcher 继承 infer_market 静态方法。"""
        assert hasattr(fetcher, "infer_market")
        assert TrendFetcher.infer_market("600519") == 1

    def test_inherits_convert_methods(self, fetcher):
        """TrendFetcher 继承基类的单位换算方法。"""
        assert hasattr(fetcher, "_convert_price")
        assert hasattr(fetcher, "_convert_volume")
        assert hasattr(fetcher, "_convert_turnover")
