#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""get_stock_concept_plates 单元测试：参数构造、关联属性解析、类型标注与过滤。

无需网络与 API，默认运行：
    pytest tests/test_concept_plates_unit.py
"""
import pytest

from tzt_api import ConceptPlateFetcher


@pytest.fixture(scope="module")
def fetcher():
    return ConceptPlateFetcher()


# 实测响应样例（688802 盛美上海，2026-08）
SAMPLE_RESPONSE = {
    "outtype": "1",
    "max": "1",
    "count": "1",
    "props": "900|901|923",
    "CoIndBlkIdx": [{
        "StockCode": ["991334"],
        "MarketSN": [44],
        "StockName": ["半导体类"],
    }],
    "CoBlkIdx": [{
        "StockCode": ["991334", "992023", "994612"],
        "MarketSN": [44, 44, 44],
        "StockName": ["半导体类", "上海", "AI芯片"],
    }],
    "RegionBlkIdx": [{
        "StockCode": ["992023"],
        "MarketSN": [44],
        "StockName": ["上海"],
    }],
}


# ============ 1. _parse_plate_group 关联属性解析 ============

class TestParsePlateGroup:
    def test_normal_parse(self, fetcher):
        plates = fetcher._parse_plate_group(SAMPLE_RESPONSE, "CoBlkIdx")
        assert len(plates) == 3
        assert plates[0] == {"code": "991334", "name": "半导体类", "market": 44}
        assert plates[2] == {"code": "994612", "name": "AI芯片", "market": 44}

    def test_missing_key_returns_empty(self, fetcher):
        assert fetcher._parse_plate_group(SAMPLE_RESPONSE, "NotExist") == []

    def test_empty_list_returns_empty(self, fetcher):
        assert fetcher._parse_plate_group({"CoBlkIdx": []}, "CoBlkIdx") == []

    def test_non_dict_inner_returns_empty(self, fetcher):
        assert fetcher._parse_plate_group({"CoBlkIdx": ["xx"]}, "CoBlkIdx") == []

    def test_missing_name_market_tolerated(self, fetcher):
        raw = {"CoBlkIdx": [{"StockCode": ["994612"]}]}
        plates = fetcher._parse_plate_group(raw, "CoBlkIdx")
        assert plates == [{"code": "994612"}]


# ============ 2. get_stock_concept_plates 参数构造与解析 ============

class TestGetStockConceptPlates:
    def _capture(self, fetcher, monkeypatch, response=SAMPLE_RESPONSE):
        captured = {}

        def fake_request(params):
            captured.update(params)
            return response

        monkeypatch.setattr(fetcher, "_request", fake_request)
        return captured

    def test_request_params(self, fetcher, monkeypatch):
        captured = self._capture(fetcher, monkeypatch)
        fetcher.get_stock_concept_plates("688802", 1)
        assert captured["Action"] == 10000
        assert captured["codes"] == "688802|1"
        assert captured["props"] == "900|901|923"
        assert captured["901.props"] == "0|1|2"
        assert captured["900.props"] == "0|1|2"
        assert captured["923.props"] == "0|1|2"
        assert captured["outtype"] == 1

    def test_market_inferred_and_prefix_stripped(self, fetcher, monkeypatch):
        captured = self._capture(fetcher, monkeypatch)
        fetcher.get_stock_concept_plates("sz000001")
        assert captured["codes"] == "000001|0"

    def test_type_annotation(self, fetcher, monkeypatch):
        self._capture(fetcher, monkeypatch)
        plates = fetcher.get_stock_concept_plates("688802", 1)
        by_code = {p["code"]: p["type"] for p in plates}
        assert by_code["991334"] == "industry"
        assert by_code["992023"] == "region"
        assert by_code["994612"] == "concept"

    def test_filter_concept(self, fetcher, monkeypatch):
        self._capture(fetcher, monkeypatch)
        plates = fetcher.get_stock_concept_plates("688802", 1, plate_type="concept")
        assert [p["code"] for p in plates] == ["994612"]

    def test_filter_industry(self, fetcher, monkeypatch):
        self._capture(fetcher, monkeypatch)
        plates = fetcher.get_stock_concept_plates("688802", 1, plate_type="industry")
        assert [p["code"] for p in plates] == ["991334"]

    def test_invalid_plate_type_raises(self, fetcher, monkeypatch):
        self._capture(fetcher, monkeypatch)
        with pytest.raises(ValueError):
            fetcher.get_stock_concept_plates("688802", 1, plate_type="foo")

    def test_request_failure_returns_none(self, fetcher, monkeypatch):
        monkeypatch.setattr(fetcher, "_request", lambda params: None)
        assert fetcher.get_stock_concept_plates("688802", 1) is None

    def test_no_plate_data_returns_empty(self, fetcher, monkeypatch):
        self._capture(fetcher, monkeypatch, response={"props": "900|901|923"})
        assert fetcher.get_stock_concept_plates("688802", 1) == []

    def test_coblkidx_missing_falls_back_to_900_923(self, fetcher, monkeypatch):
        response = {
            "CoIndBlkIdx": SAMPLE_RESPONSE["CoIndBlkIdx"],
            "RegionBlkIdx": SAMPLE_RESPONSE["RegionBlkIdx"],
        }
        self._capture(fetcher, monkeypatch, response=response)
        plates = fetcher.get_stock_concept_plates("688802", 1)
        codes = {p["code"] for p in plates}
        assert codes == {"991334", "992023"}
