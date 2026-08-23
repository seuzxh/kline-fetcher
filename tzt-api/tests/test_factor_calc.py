#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_day_kline_with_factor 的 factor 数值正确性单测（#15）。

纯函数测试：patch fetch_day_kline 返回构造的 hfq/none 数据，
验证 factor = hfq_close / none_close、volume = none_volume / factor。
无需真实 API。
"""
import math
import tempfile
from unittest import mock

import pytest

from tzt_api import KLineFetcher


def _bar(date, close, volume):
    return {"date": date, "open": close, "high": close, "low": close,
            "close": close, "volume": volume, "amount": close * volume}


@pytest.fixture
def fetcher():
    """构造一个不真正请求 API 的 KLineFetcher（用临时配置）。"""
    # KLineFetcher.__init__ 会读配置文件，用包内默认配置即可
    return KLineFetcher()


class TestFactorCalculation:
    def test_factor_value(self, fetcher):
        """factor = hfq_close / none_close。"""
        hfq = [_bar("2026-06-10", close=6000.0, volume=1000),
               _bar("2026-06-11", close=6060.0, volume=2000)]
        none = [_bar("2026-06-10", close=1000.0, volume=5000),
                _bar("2026-06-11", close=1010.0, volume=6000)]

        with mock.patch.object(fetcher, "fetch_day_kline", side_effect=[hfq, none]):
            result = fetcher.fetch_day_kline_with_factor("600519", count=-2, market=1)

        assert result is not None
        assert len(result) == 2
        # factor = 6000/1000 = 6.0, 6060/1010 = 6.0
        assert result[0]["factor"] == pytest.approx(6.0)
        assert result[1]["factor"] == pytest.approx(6.0)

    def test_volume_adjusted_by_factor(self, fetcher):
        """volume = none_volume / factor（后复权成交量）。"""
        hfq = [_bar("2026-06-10", close=6000.0, volume=999)]  # hfq volume 会被覆盖
        none = [_bar("2026-06-10", close=1000.0, volume=5000)]

        with mock.patch.object(fetcher, "fetch_day_kline", side_effect=[hfq, none]):
            result = fetcher.fetch_day_kline_with_factor("600519", count=-1, market=1)

        factor = 6000.0 / 1000.0
        expected_volume = 5000 / factor  # = 833.33...
        assert result[0]["volume"] == pytest.approx(expected_volume)

    def test_none_close_zero_yields_nan_factor(self, fetcher):
        """none_close == 0 时 factor=NaN, volume=NaN。"""
        hfq = [_bar("2026-06-10", close=6000.0, volume=1000)]
        none = [_bar("2026-06-10", close=0.0, volume=5000)]  # close=0

        with mock.patch.object(fetcher, "fetch_day_kline", side_effect=[hfq, none]):
            result = fetcher.fetch_day_kline_with_factor("600519", count=-1, market=1)

        assert math.isnan(result[0]["factor"])
        assert math.isnan(result[0]["volume"])

    def test_hfq_close_zero_yields_nan_factor(self, fetcher):
        """hfq_close <= 0 时（数据源 bug），整条记录 OHLCV+factor 均为 NaN，不崩溃。"""
        hfq = [_bar("2026-06-10", close=0.0, volume=1000)]
        none = [_bar("2026-06-10", close=1000.0, volume=5000)]

        with mock.patch.object(fetcher, "fetch_day_kline", side_effect=[hfq, none]):
            result = fetcher.fetch_day_kline_with_factor("600519", count=-1, market=1)

        assert math.isnan(result[0]["factor"])
        assert math.isnan(result[0]["volume"])
        assert math.isnan(result[0]["close"])
        assert math.isnan(result[0]["open"])

    def test_hfq_close_negative_yields_nan(self, fetcher):
        """hfq_close 为负数时（数据源 bug），整条记录标记为 NaN。"""
        hfq = [_bar("2026-06-10", close=-0.5, volume=1000)]
        none = [_bar("2026-06-10", close=1.58, volume=5000)]

        with mock.patch.object(fetcher, "fetch_day_kline", side_effect=[hfq, none]):
            result = fetcher.fetch_day_kline_with_factor("600180", count=-1, market=1)

        assert math.isnan(result[0]["factor"])
        assert math.isnan(result[0]["volume"])
        assert math.isnan(result[0]["close"])

    def test_hfq_factor_less_than_one_yields_nan(self, fetcher):
        """hfq_close>0 但 factor<1 时（数据源复权计算错乱，如 600180），整条标记 NaN。"""
        hfq = [_bar("2026-08-14", close=0.225, volume=1000)]
        none = [_bar("2026-08-14", close=1.67, volume=5000)]

        with mock.patch.object(fetcher, "fetch_day_kline", side_effect=[hfq, none]):
            result = fetcher.fetch_day_kline_with_factor("600180", count=-1, market=1)

        assert math.isnan(result[0]["factor"])
        assert math.isnan(result[0]["volume"])
        assert math.isnan(result[0]["close"])
        assert math.isnan(result[0]["open"])

    def test_hfq_low_negative_close_positive_yields_nan(self, fetcher):
        """hfq_close>0 但 low<0 时（如 600180 0814: low=-12.5 close=2.25），整条标记 NaN。"""
        bar = {"date": "2026-08-14", "open": 0.25, "high": 2.25,
               "low": -1.25, "close": 2.25, "volume": 1000, "amount": 0}
        hfq = [bar]
        none = [_bar("2026-08-14", close=1.67, volume=5000)]

        with mock.patch.object(fetcher, "fetch_day_kline", side_effect=[hfq, none]):
            result = fetcher.fetch_day_kline_with_factor("600180", count=-1, market=1)

        assert math.isnan(result[0]["factor"])
        assert math.isnan(result[0]["close"])

    def test_date_missing_in_none_yields_nan(self, fetcher):
        """none 数据缺某日时，该日 factor=NaN。"""
        hfq = [_bar("2026-06-10", close=6000.0, volume=1000),
               _bar("2026-06-11", close=6060.0, volume=2000)]
        none = [_bar("2026-06-10", close=1000.0, volume=5000)]  # 缺 06-11

        with mock.patch.object(fetcher, "fetch_day_kline", side_effect=[hfq, none]):
            result = fetcher.fetch_day_kline_with_factor("600519", count=-2, market=1)

        assert result[0]["factor"] == pytest.approx(6.0)  # 06-10 正常
        assert math.isnan(result[1]["factor"])  # 06-11 缺 none → NaN
        assert math.isnan(result[1]["volume"])

    def test_hfq_failure_returns_none(self, fetcher):
        """hfq 数据获取失败返回 None。"""
        with mock.patch.object(fetcher, "fetch_day_kline", return_value=None):
            result = fetcher.fetch_day_kline_with_factor("600519", count=-1, market=1)
        assert result is None

    def test_none_failure_returns_none(self, fetcher):
        """none 数据获取失败返回 None。"""
        hfq = [_bar("2026-06-10", close=6000.0, volume=1000)]
        with mock.patch.object(fetcher, "fetch_day_kline", side_effect=[hfq, None]):
            result = fetcher.fetch_day_kline_with_factor("600519", count=-1, market=1)
        assert result is None
