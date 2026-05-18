#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import math
import os
import time
from typing import Dict, List, Optional

import requests
import yaml

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG = os.path.join(_PACKAGE_DIR, "config", "kline_config.yaml")

PRICE_SCALE = 1_000_000
TURNOVER_SCALE = 10000

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
        if code.startswith(("600", "601", "603", "605", "688", "689")):
            return MARKET_CODE_MAP["sh"]
        if code.startswith(("000", "001", "002", "003", "300", "301")):
            return MARKET_CODE_MAP["sz"]
        if code.startswith(("8", "4", "920")):
            return MARKET_CODE_MAP["bj"]
        return MARKET_CODE_MAP["sz"]

    def _throttle(self):
        interval = self.config.get("api", {}).get("request_interval", 0.1)
        elapsed = time.time() - self._last_request_time
        if elapsed < interval:
            time.sleep(interval - elapsed)
        self._last_request_time = time.time()

    def _request(self, params: Dict) -> Optional[Dict]:
        base_url = self.config.get("api", {}).get("base_url", "http://183.242.5.14:7778")
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

    def _build_params(self, code: str, klinetype: str, market: Optional[int] = None) -> Dict:
        kline_cfg = self.config.get("kline", {})
        if market is None:
            market = self.infer_market(code)

        params = {
            "Action": 10002,
            "code": code,
            "market": market,
            "klinetype": klinetype,
            "cqtype": kline_cfg.get("cqtype", 1),
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
        return round(raw / PRICE_SCALE, 4)

    @staticmethod
    def _convert_volume(raw: int, stocks_per_h: int = 100) -> float:
        return float(raw)

    @staticmethod
    def _convert_turnover(raw: int) -> float:
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

    def _parse_kline_items(self, data_list: list, klinetype: str, stocks_per_h: int = 100) -> List[Dict]:
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
                "volume": self._convert_volume(item.get("PeriodVolume", 0), stocks_per_h),
                "amount": self._convert_turnover(item.get("PeriodTurnover", 0)),
            }

            if dt["time"] is not None:
                row["time"] = dt["time"]

            result.append(row)

        return result

    def fetch_day_kline(self, code: str, count: Optional[int] = None, market: Optional[int] = None, begindate: Optional[str] = None, enddate: Optional[str] = None) -> Optional[List[Dict]]:
        klinetype = "500"
        params = self._build_params(code, klinetype, market)

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

        stocks_per_h = raw.get("StocksPerH", 100)
        if isinstance(stocks_per_h, list) and stocks_per_h:
            stocks_per_h = stocks_per_h[0]
        stocks_per_h = int(stocks_per_h) if stocks_per_h else 100

        return self._parse_kline_items(data_list[0], klinetype, stocks_per_h)

    def fetch_min_kline(self, code: str, freq: str = "1min", count: Optional[int] = None, market: Optional[int] = None, pages: int = 1) -> Optional[List[Dict]]:
        klinetype = KLINE_TYPE_MAP.get(freq)
        if klinetype is None:
            self.logger.error(f"Unsupported freq: {freq}")
            return None

        params = self._build_params(code, klinetype, market)
        if count is not None:
            params[f"{klinetype}.count"] = -abs(count)

        response_key = KLINE_RESPONSE_KEY_MAP.get(klinetype)

        if pages <= 1:
            self.logger.info(f"Fetching {freq} kline: code={code}, market={params['market']}, count={params.get(f'{klinetype}.count')}")
            raw = self._request(params)
            if raw is None:
                return None

            if not response_key or response_key not in raw:
                self.logger.warning(f"No {response_key} in response for code={code}")
                return None

            data_list = raw[response_key]
            if not data_list or len(data_list) == 0:
                self.logger.warning(f"Empty {response_key} for code={code}")
                return None

            stocks_per_h = raw.get("StocksPerH", 100)
            if isinstance(stocks_per_h, list) and stocks_per_h:
                stocks_per_h = stocks_per_h[0]
            stocks_per_h = int(stocks_per_h) if stocks_per_h else 100

            return self._parse_kline_items(data_list[0], klinetype, stocks_per_h)

        all_data = []
        locator = None
        stocks_per_h = 100

        for page in range(pages):
            page_params = dict(params)
            if locator is not None:
                page_params[f"{klinetype}.locator"] = locator

            self.logger.info(f"Fetching {freq} kline page {page + 1}/{pages}: code={code}, market={page_params['market']}, count={page_params.get(f'{klinetype}.count')}")
            raw = self._request(page_params)
            if raw is None:
                break

            if not response_key or response_key not in raw:
                self.logger.warning(f"No {response_key} in response for code={code} at page {page + 1}")
                break

            data_list = raw[response_key]
            if not data_list or len(data_list) == 0:
                self.logger.info(f"Empty {response_key} for code={code} at page {page + 1}, stopping pagination")
                break

            sp_h = raw.get("StocksPerH", 100)
            if isinstance(sp_h, list) and sp_h:
                sp_h = sp_h[0]
            sp_h = int(sp_h) if sp_h else 100
            if page == 0:
                stocks_per_h = sp_h

            parsed = self._parse_kline_items(data_list[0], klinetype, stocks_per_h)
            if not parsed:
                break
            all_data.extend(parsed)

            locator_val = raw.get(f"{klinetype}.locator")
            if isinstance(locator_val, list) and len(locator_val) > 0 and isinstance(locator_val[0], list) and len(locator_val[0]) > 0:
                locator = locator_val[0][0]
            else:
                break

        if not all_data:
            return None

        seen = set()
        unique_data = []
        for d in sorted(all_data, key=lambda x: f"{x.get('date','')} {x.get('time','')}"):
            key = f"{d.get('date','')} {d.get('time','')}"
            if key not in seen:
                seen.add(key)
                unique_data.append(d)

        return unique_data

    def fetch_kline(self, code: str, freq: str, starttime: str, count: int, market: Optional[int] = None) -> Optional[List[Dict]]:
        parts = starttime.strip().split(" ", 1)
        if len(parts) != 2:
            self.logger.error(f"Invalid starttime format: {starttime}, expected 'yyyy-mm-dd HH:mm'")
            return None
        start_date, start_time = parts

        pages = max(1, math.ceil(abs(count) / 1500))

        raw_data = self.fetch_min_kline(code, freq=freq, count=-1500, market=market, pages=pages)
        if not raw_data:
            return None

        start_pos = None
        if count >= 0:
            for i, d in enumerate(raw_data):
                dt_str = f"{d['date']} {d['time']}"
                if dt_str >= starttime:
                    start_pos = i
                    break
        else:
            for i in range(len(raw_data) - 1, -1, -1):
                dt_str = f"{raw_data[i]['date']} {raw_data[i]['time']}"
                if dt_str <= starttime:
                    start_pos = i
                    break

        if start_pos is None:
            return None

        if count >= 0:
            return raw_data[start_pos:start_pos + count]
        else:
            begin = max(0, start_pos + count + 1)
            return raw_data[begin:start_pos + 1]

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
