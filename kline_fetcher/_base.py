#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KLineFetcher 基类：中焯行情 API 共享底座 + 日K线方法。

本模块包含：
  - 模块常量与 AdjustType 枚举、_resolve_adjust 辅助
  - KLineFetcher 基类：__init__ / 配置加载 / 限流 / 通用请求 / 参数构造 /
    字段单位换算 / K线解析
  - 日K线获取方法：fetch_day_kline / fetch_day_kline_with_factor /
    fetch_trade_calendar / get_stock_info

分钟K线方法见 kline_fetcher.min_kline.MinKLineFetcher，
概念板块方法见 kline_fetcher.concept_plate.ConceptPlateFetcher。
"""

import logging
import os
import time
from enum import IntEnum
from typing import Dict, List, Optional

import requests
import yaml

__all__ = [
    "AdjustType",
    "ADJUST_MAP",
    "_resolve_adjust",
    "PRICE_SCALE",
    "TURNOVER_SCALE",
    "MARKET_CODE_MAP",
    "KLINE_TYPE_MAP",
    "KLINE_RESPONSE_KEY_MAP",
    "KLineFetcher",
]

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG = os.path.join(_PACKAGE_DIR, "config", "kline_config.yaml")

# 中焯行情 API 原始字段单位换算系数（2026-06 实测确认，对照东财/新浪公开基准）：
#   - 价格类 (OpenPrice/HighPrice/LowPrice/ClosePrice)：原始为「万分之一元」，÷1e6 → 元
#   - 成交额 (PeriodTurnover)：原始为「万元」，÷1e4 → 元
#   - 成交量 (PeriodVolume)：原始已是「股」，无需换算（见 _convert_volume）
PRICE_SCALE = 1_000_000
TURNOVER_SCALE = 10000


class AdjustType(IntEnum):
    none = 0
    qfq = 1
    hfq = 2


ADJUST_MAP = {
    "qfq": AdjustType.qfq,
    "hfq": AdjustType.hfq,
    "none": AdjustType.none,
}


def _resolve_adjust(adjust: Optional[str]) -> Optional[int]:
    if adjust is None:
        return None
    key = adjust.lower().strip()
    if key in ADJUST_MAP:
        return int(ADJUST_MAP[key])
    try:
        return int(adjust)
    except (ValueError, TypeError):
        raise ValueError(f"无效的复权参数: {adjust}，可选值: qfq(前复权), hfq(后复权), none(不复权)")


MARKET_CODE_MAP = {
    "sh": 1,
    "sz": 0,
    "bj": 103,
}

KLINE_TYPE_MAP = {
    "day": "500",
    "1min": "501",
    "5min": "502",
    "15min": "565",
    "30min": "566",
    "60min": "567",
    "week": "561",
    "month": "562",
}

KLINE_RESPONSE_KEY_MAP = {
    "500": "DayKLine",
    "501": "Min1KLine",
    "502": "Min5KLine",
    "565": "Min15KLine",
    "566": "Min30KLine",
    "567": "Min60KLine",
    "561": "WeekKLine",
    "562": "MonthKLine",
}


class KLineFetcher:
    """中焯行情 API 客户端基类。

    提供 HTTP 请求、限流重试、参数构造、字段单位换算、K线解析等通用能力，
    以及日K线获取方法。分钟K线见 MinKLineFetcher，概念板块见 ConceptPlateFetcher。
    """

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = os.environ.get("KLINE_CONFIG_PATH", _DEFAULT_CONFIG)
        self.config = self._load_config(config_path)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session = requests.Session()
        self._last_request_time = 0.0

    def _load_config(self, config_path: str) -> Dict:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    @staticmethod
    def infer_market(code: str) -> int:
        upper = code.upper()
        if upper.startswith("SH"):
            return MARKET_CODE_MAP["sh"]
        if upper.startswith("SZ"):
            return MARKET_CODE_MAP["sz"]
        if upper.startswith("BJ"):
            return MARKET_CODE_MAP["bj"]
        numeric = code.lstrip("SHshSZszBJbj")
        if numeric.startswith(("600", "601", "603", "605", "688", "689")):
            return MARKET_CODE_MAP["sh"]
        if numeric.startswith(("000", "001", "002", "003", "300", "301")):
            return MARKET_CODE_MAP["sz"]
        if numeric.startswith(("8", "4", "920")):
            return MARKET_CODE_MAP["bj"]
        return MARKET_CODE_MAP["sz"]

    def _throttle(self):
        interval = self.config.get("api", {}).get("request_interval", 0.1)
        elapsed = time.time() - self._last_request_time
        if elapsed < interval:
            time.sleep(interval - elapsed)
        self._last_request_time = time.time()

    def _request(self, params: Dict) -> Optional[Dict]:
        base_url = os.environ.get("KLINE_API_BASE_URL") or self.config.get("api", {}).get("base_url", "")
        if not base_url:
            raise EnvironmentError(
                "API base URL is not configured. "
                "Set the KLINE_API_BASE_URL environment variable (e.g. in .env or as a GitHub Secret/Variable), "
                "or set api.base_url in your kline_config.yaml."
            )
        timeout = self.config.get("api", {}).get("timeout", 10)
        max_retries = self.config.get("api", {}).get("max_retries", 3)
        retry_delay = self.config.get("api", {}).get("retry_delay", 1)

        for attempt in range(max_retries):
            self._throttle()
            try:
                resp = self.session.get(
                    f"{base_url}/reqxml",
                    params=params,
                    timeout=timeout,
                )
                resp.raise_for_status()
                result = resp.json()

                error_no = result.get("ErrorNo")
                if error_no and str(error_no) != "0":
                    self.logger.warning(
                        f"API error: {result.get('ErrorMessage', 'unknown')} "
                        f"(ErrorNo={error_no}, attempt {attempt + 1})"
                    )
                    time.sleep(retry_delay * (2 ** attempt))
                    continue

                return result

            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Request error: {e} (attempt {attempt + 1})")
                time.sleep(retry_delay * (2 ** attempt))
            except Exception as e:
                self.logger.warning(f"Parse error: {e} (attempt {attempt + 1})")
                time.sleep(retry_delay * (2 ** attempt))

        self.logger.error(f"API request failed after {max_retries} retries: params={params}")
        return None

    def _build_params(self, code: str, klinetype: str, market: Optional[int] = None, adjust: Optional[str] = None) -> Dict:
        kline_cfg = self.config.get("kline", {})
        if market is None:
            market = self.infer_market(code)

        numeric_code = code.lstrip("SHshSZszBJbj") or code

        cqtype_val = _resolve_adjust(adjust)
        if cqtype_val is None:
            cqtype_val = kline_cfg.get("cqtype", 2)

        params = {
            "Action": 10002,
            "code": numeric_code,
            "market": market,
            "klinetype": klinetype,
            "cqtype": cqtype_val,
            "props": kline_cfg.get("props", "0|1|2|3|4|191|190|519"),
            "outtype": kline_cfg.get("outtype", 1),
            "rights": kline_cfg.get("rights", 0),
            "Route": kline_cfg.get("route", 1),
        }

        count_key = f"{klinetype}.count"
        default_count = kline_cfg.get("day_count", -5000) if klinetype == "500" else kline_cfg.get("min_count", -2400)
        params[count_key] = default_count

        return params

    @staticmethod
    def _convert_price(raw: int) -> float:
        """中焯价格字段（万分之一元）→ 元。"""
        return round(raw / PRICE_SCALE, 4)

    @staticmethod
    def _convert_volume(raw: int) -> float:
        """成交量：中焯 PeriodVolume 原始单位即「股」，直接使用。

        实测确认（2026-06，贵州茅台 600519 对照东财/新浪公开基准，
        中焯值/新浪值 = 1.0000；成交额÷成交量≈股价，自洽）：单位为「股」，
        无需按「手→股」做 ×100 换算。
        """
        return float(raw)

    @staticmethod
    def _convert_turnover(raw: int) -> float:
        """中焯成交额字段（万元）→ 元。"""
        return round(raw / TURNOVER_SCALE, 2)

    @staticmethod
    def _convert_datetime(time_raw: int, klinetype: str) -> Dict[str, Optional[str]]:
        time_str = str(time_raw).zfill(14)
        if len(time_str) != 14:
            return {"date": "", "time": None}
        date = f"{time_str[0:4]}-{time_str[4:6]}-{time_str[6:8]}"
        if klinetype != "500":
            t = f"{time_str[8:10]}:{time_str[10:12]}:{time_str[12:14]}"
            return {"date": date, "time": t}
        return {"date": date, "time": None}

    def _parse_kline_items(self, data_list: list, klinetype: str) -> List[Dict]:
        result = []
        for item in data_list:
            if not isinstance(item, dict):
                continue
            dt = self._convert_datetime(item.get("Time", 0), klinetype)
            if not dt["date"]:
                continue

            row = {
                "date": dt["date"],
                "open": self._convert_price(item.get("OpenPrice", 0)),
                "high": self._convert_price(item.get("HighPrice", 0)),
                "low": self._convert_price(item.get("LowPrice", 0)),
                "close": self._convert_price(item.get("ClosePrice", 0)),
                "volume": self._convert_volume(item.get("PeriodVolume", 0)),
                "amount": self._convert_turnover(item.get("PeriodTurnover", 0)),
            }

            if dt["time"] is not None:
                row["time"] = dt["time"]

            result.append(row)

        return result

    # ===== 日K线方法 =====

    def fetch_day_kline(self, code: str, count: Optional[int] = None, market: Optional[int] = None, begindate: Optional[str] = None, enddate: Optional[str] = None, adjust: Optional[str] = None) -> Optional[List[Dict]]:
        klinetype = "500"
        params = self._build_params(code, klinetype, market, adjust=adjust)

        if begindate is not None or enddate is not None:
            del params[f"{klinetype}.count"]
            if begindate is not None:
                params["begindate"] = int(begindate)
            if enddate is not None:
                params["enddate"] = int(enddate)
        elif count is not None:
            params[f"{klinetype}.count"] = -abs(count)

        self.logger.info(f"Fetching day kline: code={code}, market={params['market']}, count={params.get(f'{klinetype}.count')}, begindate={params.get('begindate')}, enddate={params.get('enddate')}")
        raw = self._request(params)
        if raw is None:
            return None

        response_key = KLINE_RESPONSE_KEY_MAP.get(klinetype)
        if not response_key or response_key not in raw:
            self.logger.warning(f"No DayKLine in response for code={code}")
            return None

        data_list = raw[response_key]
        if not data_list or len(data_list) == 0:
            self.logger.warning(f"Empty DayKLine for code={code}")
            return None

        return self._parse_kline_items(data_list[0], klinetype)

    def fetch_day_kline_with_factor(self, code: str, count: Optional[int] = None, market: Optional[int] = None, begindate: Optional[str] = None, enddate: Optional[str] = None) -> Optional[List[Dict]]:
        hfq_data = self.fetch_day_kline(code, count=count, market=market, begindate=begindate, enddate=enddate, adjust="hfq")
        if hfq_data is None:
            return None
        none_data = self.fetch_day_kline(code, count=count, market=market, begindate=begindate, enddate=enddate, adjust="none")
        if none_data is None:
            self.logger.error(f"Failed to fetch none-adjust data for code={code}")
            return None
        none_by_date = {item["date"]: item for item in none_data}
        for item in hfq_data:
            none_item = none_by_date.get(item["date"])
            if none_item and none_item["close"] != 0:
                factor = float(item["close"]) / float(none_item["close"])
                item["factor"] = factor
                item["volume"] = float(none_item["volume"]) / factor
            else:
                item["factor"] = float("nan")
                item["volume"] = float("nan")
        return hfq_data

    def fetch_trade_calendar(self, start_year: int = 2000, end_year: int = 2030, index_code: str = "000001", market: int = 1) -> Optional[List[str]]:
        all_dates = []
        for year in range(end_year, start_year - 1, -1):
            begindate = f"{year}0101"
            enddate = f"{year}1231"
            data = self.fetch_day_kline(index_code, market=market, begindate=begindate, enddate=enddate)
            if data is None:
                continue
            for item in data:
                d = item.get("date", "")
                if d and d not in all_dates:
                    all_dates.append(d)
            self.logger.info(f"Fetched trade calendar for {year}: {len(data) if data else 0} dates")
        all_dates.sort()
        self.logger.info(f"Total trade dates fetched: {len(all_dates)}")
        return all_dates

    def get_stock_info(self, code: str, market: Optional[int] = None) -> Optional[Dict]:
        params = self._build_params(code, "500", market)
        params["422.daycount"] = -1
        raw = self._request(params)
        if raw is None:
            return None

        stock_code = raw.get("StockCode", "")
        stock_name = raw.get("StockName", "")
        market_sn = raw.get("MarketSN", 0)

        if isinstance(stock_code, list) and stock_code:
            stock_code = stock_code[0]
        if isinstance(stock_name, list) and stock_name:
            stock_name = stock_name[0]
        if isinstance(market_sn, list) and market_sn:
            market_sn = market_sn[0]

        return {
            "code": stock_code,
            "name": stock_name,
            "market_sn": market_sn,
        }
