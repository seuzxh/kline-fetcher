#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""server.py 在线调试服务单元测试（mock 上游 fetcher，不发起真实 API 请求）。"""

import math

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from kline_qlib import server  # noqa: E402

DAY_KLINE_MOCK = [
    {"date": "2026-08-21", "open": 1.0, "high": 2.0, "low": 0.5,
     "close": 1.5, "volume": 100, "amount": 150.0}
]

FACTOR_DIRTY_MOCK = [
    {"date": "2026-08-14", "open": float("nan"), "high": float("nan"),
     "low": float("nan"), "close": float("nan"), "factor": float("nan"),
     "volume": float("nan")}
]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server.day_fetcher(), "fetch_day_kline",
                        lambda *a, **k: [dict(d) for d in DAY_KLINE_MOCK])
    monkeypatch.setattr(server.day_fetcher(), "fetch_day_kline_with_factor",
                        lambda *a, **k: [dict(d) for d in FACTOR_DIRTY_MOCK])
    monkeypatch.setattr(server.trend_fetcher(), "fetch_intraday_trend",
                        lambda *a, **k: {"market_date": "20260821", "pre_market": [], "trading": []})
    return TestClient(server.app)


class TestOpenAPISchema:
    def test_openapi_lists_all_endpoint_groups(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        paths = resp.json()["paths"]
        for path in [
            "/api/day-kline", "/api/day-kline-with-factor", "/api/trade-calendar",
            "/api/stock-info", "/api/min-kline", "/api/trend", "/api/trend/intraday",
            "/api/trend/history", "/api/concept/plates", "/api/concept/plate-kline",
            "/api/concept/plate-stocks", "/api/concept/stock-plates", "/api/coverage",
        ]:
            assert path in paths, f"missing endpoint: {path}"

    def test_swagger_ui_served(self, client):
        assert client.get("/docs").status_code == 200

    def test_root_redirects_to_docs(self, client):
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code in (307, 302)
        assert resp.headers["location"] == "/docs"


class TestHandlerBehavior:
    def test_day_kline_returns_data(self, client):
        resp = client.get("/api/day-kline", params={"code": "600519"})
        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["date"] == "2026-08-21"
        assert body[0]["close"] == 1.5

    def test_none_result_yields_502(self, client, monkeypatch):
        monkeypatch.setattr(server.day_fetcher(), "fetch_day_kline", lambda *a, **k: None)
        resp = client.get("/api/day-kline", params={"code": "600519"})
        assert resp.status_code == 502
        assert "失败" in resp.json()["detail"]

    def test_nan_records_sanitized_to_null(self, client):
        """脏数据记录含 NaN（factor 校验失败场景），JSON 序列化为 null 而非 500。"""
        resp = client.get("/api/day-kline-with-factor", params={"code": "600180"})
        assert resp.status_code == 200
        item = resp.json()[0]
        assert item["close"] is None
        assert item["factor"] is None
        assert math.isnan(FACTOR_DIRTY_MOCK[0]["close"])  # 原始数据确为 NaN

    def test_invalid_date_format_rejected(self, client):
        resp = client.get("/api/day-kline", params={"code": "600519", "begindate": "2026-08-01"})
        assert resp.status_code == 422

    def test_invalid_adjust_rejected(self, client):
        resp = client.get("/api/day-kline", params={"code": "600519", "adjust": "xxx"})
        assert resp.status_code == 422

    def test_trend_intraday_passthrough(self, client):
        resp = client.get("/api/trend/intraday", params={"code": "600519"})
        assert resp.status_code == 200
        assert resp.json()["market_date"] == "20260821"


class TestCoverage:
    def test_unknown_code_not_covered(self, client):
        resp = client.get("/api/coverage", params={"code": "999999"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["covered"] is False
