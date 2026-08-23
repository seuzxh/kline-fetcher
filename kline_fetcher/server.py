#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kline-fetcher 在线调试服务：FastAPI 薄包装，自带 Swagger UI。

把各 Fetcher 的获取方法与 KLineToQlib 的本地查询方法映射为 REST 端点，
浏览器打开 /docs 即可填参数在线测试（Swagger UI），也可用 /redoc 看文档。

启动：
    kline-server                        # http://127.0.0.1:8000/docs
    kline-server --port 9000
    uvicorn kline_fetcher.server:app    # 等效

依赖：pip install 'kline-fetcher[server]'
环境：需设置 KLINE_API_BASE_URL（数据获取类端点才需要）

注意：本服务无鉴权（中焯 API 本身无 Token），默认只绑定 127.0.0.1，
请勿暴露到公网。只暴露读操作（获取/查询），不暴露 bin 写入，防止误写数据。
"""
import argparse
import math
from functools import lru_cache
from typing import Any, List, Literal, Optional

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import RedirectResponse
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "server 功能需要 fastapi/uvicorn，请安装可选依赖："
        "pip install 'kline-fetcher[server]'"
    ) from e

from kline_fetcher import (
    __version__,
    ConceptPlateFetcher,
    KLineFetcher,
    KLineToQlib,
    MinKLineFetcher,
    TrendFetcher,
)

app = FastAPI(
    title="kline-fetcher 在线调试服务",
    description=(
        "中焯行情 API 客户端的在线测试页。每个端点对应一个 Fetcher 方法，"
        "参数与 Python API 一致。失败时返回 502，原因见服务端日志；"
        "脏数据记录中的 NaN 在 JSON 中序列化为 null。"
    ),
    version=__version__,
)


# ===== 惰性单例：限流基于实例时间戳，共享实例即全局限流 =====

@lru_cache(maxsize=1)
def day_fetcher() -> KLineFetcher:
    return KLineFetcher()


@lru_cache(maxsize=1)
def min_fetcher() -> MinKLineFetcher:
    return MinKLineFetcher()


@lru_cache(maxsize=1)
def trend_fetcher() -> TrendFetcher:
    return TrendFetcher()


@lru_cache(maxsize=1)
def plate_fetcher() -> ConceptPlateFetcher:
    return ConceptPlateFetcher()


@lru_cache(maxsize=1)
def converter() -> KLineToQlib:
    return KLineToQlib()


# ===== 响应处理 =====

def _json_safe(obj: Any) -> Any:
    """NaN/Inf → None。Starlette JSONResponse 为 allow_nan=False，
    factor 脏数据记录含 NaN，不转换会导致响应 500。"""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    return obj


def _or_502(data: Any, action: str) -> Any:
    if data is None:
        raise HTTPException(status_code=502, detail=f"{action} 失败或无数据，原因见服务端日志")
    return _json_safe(data)


def _idx_to_date(conv: KLineToQlib, freq: str, idx: Optional[int]) -> Optional[str]:
    cal = conv.dates if freq == "day" else conv.min_calendars.get(freq, [])
    if idx is None or not cal or not 0 <= idx < len(cal):
        return None
    return cal[idx]


# ===== 端点：日K线（KLineFetcher） =====

@app.get("/api/day-kline", tags=["日K线"], summary="获取日K线 fetch_day_kline")
def get_day_kline(
    code: str = Query(..., description="股票/指数代码：600519 / sh600519 / 000300（裸码按指数优先）"),
    count: Optional[int] = Query(None, description="条数（从最新向前，负值语义）"),
    market: Optional[int] = Query(None, description="市场：1=沪 0=深 103=北；缺省自动推断"),
    begindate: Optional[str] = Query(None, pattern=r"^\d{8}$", description="开始日期 YYYYMMDD（设置后 count 失效）"),
    enddate: Optional[str] = Query(None, pattern=r"^\d{8}$", description="结束日期 YYYYMMDD"),
    adjust: Optional[Literal["qfq", "hfq", "none"]] = Query(None, description="复权方式；缺省用配置默认（后复权）"),
):
    data = day_fetcher().fetch_day_kline(
        code, count=count, market=market, begindate=begindate, enddate=enddate, adjust=adjust
    )
    return _or_502(data, f"获取 {code} 日K线")


@app.get("/api/day-kline-with-factor", tags=["日K线"], summary="获取日K线（含factor） fetch_day_kline_with_factor")
def get_day_kline_with_factor(
    code: str = Query(..., description="股票代码，如 600519"),
    count: Optional[int] = Query(None, description="条数（从最新向前）"),
    market: Optional[int] = Query(None, description="市场：1=沪 0=深 103=北；缺省自动推断"),
    begindate: Optional[str] = Query(None, pattern=r"^\d{8}$", description="开始日期 YYYYMMDD"),
    enddate: Optional[str] = Query(None, pattern=r"^\d{8}$", description="结束日期 YYYYMMDD"),
):
    data = day_fetcher().fetch_day_kline_with_factor(
        code, count=count, market=market, begindate=begindate, enddate=enddate
    )
    return _or_502(data, f"获取 {code} 后复权日K线（含factor）")


@app.get("/api/trade-calendar", tags=["日K线"], summary="获取交易日历 fetch_trade_calendar")
def get_trade_calendar(
    start_year: int = Query(2000, ge=1990, le=2100),
    end_year: int = Query(2030, ge=1990, le=2100, description="含边界"),
):
    return _or_502(day_fetcher().fetch_trade_calendar(start_year=start_year, end_year=end_year), "获取交易日历")


@app.get("/api/stock-info", tags=["日K线"], summary="获取股票基本信息 get_stock_info")
def get_stock_info(
    code: str = Query(..., description="股票代码，如 600519"),
    market: Optional[int] = Query(None, description="市场：1=沪 0=深 103=北；缺省自动推断"),
):
    return _or_502(day_fetcher().get_stock_info(code, market=market), f"获取 {code} 基本信息")


# ===== 端点：分钟K线（MinKLineFetcher） =====

@app.get("/api/min-kline", tags=["分钟K线"], summary="获取分钟K线 fetch_min_kline")
def get_min_kline(
    code: str = Query(..., description="股票/指数代码，如 600519"),
    freq: Literal["1min", "5min", "15min", "30min", "60min"] = Query("1min", description="频率"),
    count: Optional[int] = Query(None, description="单页条数（从最新向前）"),
    market: Optional[int] = Query(None, description="市场：1=沪 0=深 103=北；缺省自动推断"),
    pages: int = Query(1, ge=1, description="翻页次数，>1 时按 locator 自动翻页并去重"),
    adjust: Optional[Literal["qfq", "hfq", "none"]] = Query(None, description="复权方式；缺省用配置默认"),
):
    data = min_fetcher().fetch_min_kline(
        code, freq=freq, count=count, market=market, pages=pages, adjust=adjust
    )
    return _or_502(data, f"获取 {code} {freq} K线")


# ===== 端点：分时数据（TrendFetcher） =====

@app.get("/api/trend/intraday", tags=["分时数据"], summary="获取当日分时 fetch_intraday_trend")
def get_intraday_trend(
    code: str = Query(..., description="股票/指数代码，如 600519 / 000300"),
    market: Optional[int] = Query(None, description="市场；缺省自动推断"),
):
    return _or_502(trend_fetcher().fetch_intraday_trend(code, market=market), f"获取 {code} 当日分时")


@app.get("/api/trend/history", tags=["分时数据"], summary="获取历史分时 fetch_history_trend")
def get_history_trend(
    code: str = Query(..., description="股票/指数代码"),
    date: str = Query(..., pattern=r"^\d{8}$", description="历史日期 YYYYMMDD"),
    market: Optional[int] = Query(None, description="市场；缺省自动推断"),
):
    return _or_502(trend_fetcher().fetch_history_trend(code, date, market=market), f"获取 {code} {date} 历史分时")


@app.get("/api/trend", tags=["分时数据"], summary="获取分时（自动判断当日/历史） fetch_trend")
def get_trend(
    code: str = Query(..., description="股票/指数代码"),
    date: Optional[str] = Query(None, pattern=r"^\d{8}$", description="YYYYMMDD；缺省或 0 取当日"),
    market: Optional[int] = Query(None, description="市场；缺省自动推断"),
):
    return _or_502(trend_fetcher().fetch_trend(code, date=date, market=market), f"获取 {code} 分时数据")


# ===== 端点：概念板块（ConceptPlateFetcher） =====

@app.get("/api/concept/plates", tags=["概念板块"], summary="获取概念板块列表 get_all_concept_plates（仅前 30 个）")
def get_concept_plates():
    return _or_502(plate_fetcher().get_all_concept_plates(), "获取概念板块列表")


@app.get("/api/concept/plate-kline", tags=["概念板块"], summary="获取板块日K线 get_concept_plate_kline")
def get_concept_plate_kline(
    plate_code: str = Query(..., description="板块代码，如 994612"),
    count: int = Query(-220, description="条数（从最新向前）"),
    market: int = Query(44, description="板块市场固定 44"),
):
    return _or_502(
        plate_fetcher().get_concept_plate_kline(plate_code, count=count, market=market),
        f"获取板块 {plate_code} 日K线",
    )


@app.get("/api/concept/plate-stocks", tags=["概念板块"], summary="获取板块成份股 get_concept_plate_stocks（首项为板块自身）")
def get_concept_plate_stocks(
    plate_code: str = Query(..., description="板块代码，如 994612"),
    start: int = Query(0, ge=0, description="分页起始位置"),
    count: int = Query(10, ge=1, le=100, description="每页数量"),
):
    return _or_502(
        plate_fetcher().get_concept_plate_stocks(plate_code, start=start, count=count),
        f"获取板块 {plate_code} 成份股",
    )


@app.get("/api/concept/stock-plates", tags=["概念板块"], summary="获取股票所属板块 get_stock_concept_plates（属性 900/901/923）")
def get_stock_concept_plates(
    code: str = Query(..., description="股票代码，如 600519"),
    market: Optional[int] = Query(None, description="市场：1=沪 0=深 103=北（可选，默认自动推断）"),
    plate_type: Optional[str] = Query(None, description="板块类型过滤：concept/industry/region（可选，默认全部）"),
):
    return _or_502(plate_fetcher().get_stock_concept_plates(code, market, plate_type=plate_type), f"获取 {code} 所属板块")


# ===== 端点：本地数据查询（KLineToQlib，只读） =====

@app.get("/api/coverage", tags=["本地数据查询"], summary="检查本地 bin 覆盖范围 check_local_coverage")
def get_coverage(
    code: str = Query(..., description="股票代码，如 600519"),
    field: str = Query("close", description="字段名（bin 文件名）"),
    freq: Literal["day", "1min", "5min", "15min", "30min", "60min"] = Query("day"),
    qlib_dir: Optional[str] = Query(None, description="显式指定目录名，缺省按 code 推断"),
    nan_aware: bool = Query(False, description="True 时按最后一个非 NaN 槽计算覆盖（检测伪覆盖）"),
):
    conv = converter()
    start_idx, end_idx = conv.check_local_coverage(
        code, field=field, freq=freq, qlib_dir=qlib_dir, nan_aware=nan_aware
    )
    if start_idx is None:
        return {"code": code, "field": field, "freq": freq, "covered": False}
    return {
        "code": code,
        "field": field,
        "freq": freq,
        "covered": True,
        "start_idx": start_idx,
        "end_idx": end_idx,
        "start": _idx_to_date(conv, freq, start_idx),
        "end": _idx_to_date(conv, freq, end_idx),
    }


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


def main():
    parser = argparse.ArgumentParser(description="kline-fetcher 在线调试服务（Swagger UI）")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1；无鉴权，勿暴露公网）")
    parser.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    parser.add_argument("--reload", action="store_true", help="开发模式：代码变更自动重启")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:  # pragma: no cover
        raise SystemExit("缺少 uvicorn，请安装：pip install 'kline-fetcher[server]'")

    uvicorn.run("kline_fetcher.server:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
