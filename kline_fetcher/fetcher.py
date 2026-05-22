#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import math
import os
import time
from enum import IntEnum
from typing import Dict, List, Optional

import requests
import yaml

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG = os.path.join(_PACKAGE_DIR, "config", "kline_config.yaml")

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

        stocks_per_h = raw.get("StocksPerH", 100)
        if isinstance(stocks_per_h, list) and stocks_per_h:
            stocks_per_h = stocks_per_h[0]
        stocks_per_h = int(stocks_per_h) if stocks_per_h else 100

        return self._parse_kline_items(data_list[0], klinetype, stocks_per_h)

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

    def fetch_min_kline(self, code: str, freq: str = "1min", count: Optional[int] = None, market: Optional[int] = None, pages: int = 1, adjust: Optional[str] = None) -> Optional[List[Dict]]:
        klinetype = KLINE_TYPE_MAP.get(freq)
        if klinetype is None:
            self.logger.error(f"Unsupported freq: {freq}")
            return None

        params = self._build_params(code, klinetype, market, adjust=adjust)
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

    def fetch_kline(self, code: str, freq: str, starttime: str, count: int, market: Optional[int] = None, adjust: Optional[str] = None) -> Optional[List[Dict]]:
        parts = starttime.strip().split(" ", 1)
        if len(parts) != 2:
            self.logger.error(f"Invalid starttime format: {starttime}, expected 'yyyy-mm-dd HH:mm'")
            return None
        start_date, start_time = parts

        pages = max(1, math.ceil(abs(count) / 1500))

        raw_data = self.fetch_min_kline(code, freq=freq, count=-1500, market=market, pages=pages, adjust=adjust)
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

    def get_all_concept_plates(self) -> Optional[List[Dict]]:
        """获取所有概念板块列表。
        
        从API获取A股所有概念板块的基本信息，包括板块代码、名称、市场代码以及
        可能的行情数据（最新价、涨跌额、涨跌幅）。
        
        参数:
            无
            
        返回值:
            Optional[List[Dict]]: 概念板块列表，每个板块是一个字典，包含以下键：
                - code (str): 板块代码
                - name (str): 板块名称
                - market (int): 市场代码（44表示概念板块市场）
                - price (int, optional): 最新价（原始整数格式）
                - change (int, optional): 涨跌额（原始整数格式）
                - change_pct (int, optional): 涨跌幅（原始整数格式）
            如果请求失败，返回 None。
            
        使用示例:
            >>> fetcher = KLineFetcher()
            >>> plates = fetcher.get_all_concept_plates()
            >>> if plates:
            ...     for plate in plates[:5]:  # 只显示前5个
            ...         print(f"{plate['code']} - {plate['name']}")
        """
        kline_cfg = self.config.get("kline", {})
        params = {
            "Action": 10007,
            "needtitle": 1,
            "subtype": 1,
            "rights": kline_cfg.get("rights", 0),
            "direction": 1,
            "906.props": "0|2|10|514",
            "start": 0,
            "count": 30,
            "groups": "HQ_StockInfo|HQ_StockProp",
            "sort": 514,
            "props": "10|510|514|573|4|575|5|574|6|576|7|577|12|13|21|551|513|521|23|906|751|752|753|754|755|756|757|11",
            "market": 44,
            "Route": kline_cfg.get("route", 1),
        }

        # 发送API请求
        raw = self._request(params)
        if raw is None:
            return None

        # 初始化结果列表
        plates = []
        
        # 检查响应中是否包含必要的字段
        if "StockCode" in raw and "StockName" in raw and "MarketSN" in raw:
            codes = raw["StockCode"]
            names = raw["StockName"]
            markets = raw["MarketSN"]
            
            # 遍历所有概念板块
            for i in range(len(codes)):
                # 构建板块基本信息
                plate = {
                    "code": codes[i],
                    "name": names[i],
                    "market": markets[i]
                }
                
                # 添加可选的行情数据字段（如果响应中存在）
                if "QuoteLast" in raw and i < len(raw["QuoteLast"]):
                    plate["price"] = raw["QuoteLast"][i]
                if "PxChg" in raw and i < len(raw["PxChg"]):
                    plate["change"] = raw["PxChg"][i]
                if "PxChgPct" in raw and i < len(raw["PxChgPct"]):
                    plate["change_pct"] = raw["PxChgPct"][i]
                
                plates.append(plate)
        
        self.logger.info(f"Fetched {len(plates)} concept plates")
        return plates

    def get_concept_plate_kline(self, plate_code: str, count: int = -220, market: int = 44) -> Optional[List[Dict]]:
        """获取指定概念板块的日K线数据。
        
        从API获取指定概念板块的历史日K线数据，包括开盘价、最高价、最低价、
        收盘价、成交量和成交额等信息。默认获取最近220个交易日的数据。
        
        参数:
            plate_code (str): 概念板块代码，例如 "994612"
            count (int, optional): K线数量，负值表示从最新数据向前获取，
                正值表示从某个时间点向后获取。默认值为 -220，表示获取
                最近220个交易日的K线数据。
            market (int, optional): 市场代码，44表示概念板块市场。默认值为 44。
            
        返回值:
            Optional[List[Dict]]: K线数据列表，每个元素是一个字典，包含以下键：
                - date (str): 日期，格式为 "yyyy-mm-dd"
                - open (float): 开盘价
                - high (float): 最高价
                - low (float): 最低价
                - close (float): 收盘价
                - volume (float): 成交量
                - amount (float): 成交额（单位：万元）
            如果请求失败或无数据，返回 None。
            
        使用示例:
            >>> fetcher = KLineFetcher()
            >>> kline_data = fetcher.get_concept_plate_kline("994612")
            >>> if kline_data:
            ...     print(f"共获取 {len(kline_data)} 条K线数据")
            ...     print(f"最新K线: {kline_data[0]}")
            >>> # 获取最近100条K线
            >>> kline_data_short = fetcher.get_concept_plate_kline("994612", count=-100)
        """
        klinetype = "500"
        kline_cfg = self.config.get("kline", {})
        params = {
            "Action": 10002,
            "code": plate_code,
            "market": market,
            "klinetype": klinetype,
            "cqType": 0,
            "props": kline_cfg.get("props", "0|1|2|3|4|191|190|519"),
            "422.daycount": -220,
            f"{klinetype}.count": count,
            "Route": kline_cfg.get("route", 1),
        }

        # 发送API请求
        raw = self._request(params)
        if raw is None:
            return None

        # 获取对应的响应键名
        response_key = KLINE_RESPONSE_KEY_MAP.get(klinetype)
        if not response_key or response_key not in raw:
            self.logger.warning(f"No {response_key} in response for plate_code={plate_code}")
            return None

        # 提取K线数据列表
        data_list = raw[response_key]
        if not data_list or len(data_list) == 0:
            self.logger.warning(f"Empty {response_key} for plate_code={plate_code}")
            return None

        # 获取每手股数（用于成交量转换）
        stocks_per_h = raw.get("StocksPerH", 100)
        if isinstance(stocks_per_h, list) and stocks_per_h:
            stocks_per_h = stocks_per_h[0]
        stocks_per_h = int(stocks_per_h) if stocks_per_h else 100

        # 解析并返回K线数据
        return self._parse_kline_items(data_list[0], klinetype, stocks_per_h)

    def get_concept_plate_stocks(self, plate_code: str, start: int = 0, count: int = 10) -> Optional[List[Dict]]:
        """获取指定概念板块的成份股列表。
        
        从API获取指定概念板块的成份股信息，包括股票代码、名称、市场代码以及
        可能的行情数据（最新价、涨跌额、涨跌幅、最高价、最低价）。支持分页获取。
        
        参数:
            plate_code (str): 概念板块代码，例如 "994612"
            start (int, optional): 分页起始位置，从 0 开始。默认值为 0。
            count (int, optional): 每页获取的股票数量。默认值为 10。
            
        返回值:
            Optional[List[Dict]]: 成份股列表，每个股票是一个字典，包含以下键：
                - code (str): 股票代码
                - name (str): 股票名称
                - market (int): 市场代码（0表示深圳，1表示上海，103表示北京）
                - price (int, optional): 最新价（原始整数格式）
                - change (int, optional): 涨跌额（原始整数格式）
                - change_pct (int, optional): 涨跌幅（原始整数格式）
                - high (int, optional): 最高价（原始整数格式）
                - low (int, optional): 最低价（原始整数格式）
            如果请求失败，返回 None。
            
        使用示例:
            >>> fetcher = KLineFetcher()
            >>> # 获取某个概念板块的前10只成份股
            >>> stocks = fetcher.get_concept_plate_stocks("994612")
            >>> if stocks:
            ...     for stock in stocks:
            ...         print(f"{stock['code']} - {stock['name']}")
            >>> # 获取某个概念板块的第11-20只成份股
            >>> stocks_page2 = fetcher.get_concept_plate_stocks("994612", start=10, count=10)
        """
        # 构建请求参数
        kline_cfg = self.config.get("kline", {})
        params = {
            "Action": 10005,
            "block.include": 1,
            "block.type": 1,
            "needtitle": 1,
            "rights": kline_cfg.get("rights", 0),
            "block": plate_code,
            "direction": 1,
            "start": start,
            "count": count,
            "groups": "HQ_StockInfo|HQ_StockProp",
            "sort": 514,
            "props": "710|560|514|10|4|6|7|60|61|62|11|510|711",
            "Route": kline_cfg.get("route", 1),
            "routemarkets": 44,
        }

        # 发送API请求
        raw = self._request(params)
        if raw is None:
            return None

        # 解析成份股数据
        stocks = []
        # 检查响应中是否包含必要的字段
        if "StockCode" in raw and "StockName" in raw and "MarketSN" in raw:
            codes = raw["StockCode"]
            names = raw["StockName"]
            markets = raw["MarketSN"]
            
            # 遍历所有成份股
            for i in range(len(codes)):
                # 构建股票基本信息
                stock = {
                    "code": codes[i],
                    "name": names[i],
                    "market": markets[i]
                }
                # 添加可选的行情数据字段（如果响应中存在）
                if "QuoteLast" in raw and i < len(raw["QuoteLast"]):
                    stock["price"] = raw["QuoteLast"][i]
                if "PxChg" in raw and i < len(raw["PxChg"]):
                    stock["change"] = raw["PxChg"][i]
                if "PxChgPct" in raw and i < len(raw["PxChgPct"]):
                    stock["change_pct"] = raw["PxChgPct"][i]
                if "High" in raw and i < len(raw["High"]):
                    stock["high"] = raw["High"][i]
                if "Low" in raw and i < len(raw["Low"]):
                    stock["low"] = raw["Low"][i]
                stocks.append(stock)
        
        self.logger.info(f"Fetched {len(stocks)} stocks for plate {plate_code}")
        return stocks

    def get_stock_concept_plates(self, code: str, market: int) -> Optional[List[Dict]]:
        """获取指定股票所属的概念板块列表。
        
        从API获取指定股票所属的所有概念板块信息，包括板块代码和名称。
        该方法会尝试多种解析策略，以适应API响应格式的变化。
        
        参数:
            code (str): 股票代码，例如 "600519"
            market (int): 市场代码，0表示深圳，1表示上海，103表示北京
            
        返回值:
            Optional[List[Dict]]: 概念板块列表，每个板块是一个字典，包含以下键：
                - code (str): 板块代码
                - name (str, optional): 板块名称（如果API返回）
            如果请求失败，返回 None。
            
        使用示例:
            >>> fetcher = KLineFetcher()
            >>> # 获取贵州茅台（600519）所属的概念板块
            >>> plates = fetcher.get_stock_concept_plates("600519", 1)
            >>> if plates:
            ...     print(f"贵州茅台共属于 {len(plates)} 个概念板块")
            ...     for plate in plates:
            ...         print(f"  - {plate.get('name', '未知')} ({plate['code']})")
        """
        # 构建API请求参数
        kline_cfg = self.config.get("kline", {})
        params = {
            "Action": 10000,
            "codes": f"{code}|{market}",
            "count": 1,
            "groups": "HQ_StockInfo",
            "props": "11|10|147|19|20|13|521|22|23|320|554|555|1034|553|1001|550|1040|552|1033|124|125|135|134|104|105|141|142|289|422|131|132|133|190|191|1039|1|",
            "market": market,
            "reqlinktype": 0,
            "outtype": kline_cfg.get("outtype", 1),
        }

        # 发送API请求
        raw = self._request(params)
        if raw is None:
            return None

        # 初始化概念板块列表
        concept_plates = []
        
        # 策略1：查找包含 "Block" 或 "Concept" 关键词的字段
        # 可能的字段名：BlockCode, BlockName, ConceptCode, ConceptName 等
        block_fields = []
        for key in raw.keys():
            if "Block" in key or "Concept" in key:
                block_fields.append(key)
        
        if block_fields:
            # 假设第一个找到的字段是板块代码字段
            code_field = block_fields[0]
            # 检查板块代码字段是否为列表类型
            if isinstance(raw[code_field], list):
                # 遍历所有板块代码
                for i, plate_code in enumerate(raw[code_field]):
                    # 构建板块基本信息
                    plate = {
                        "code": plate_code
                    }
                    # 在其他板块相关字段中查找对应的板块名称
                    for name_field in block_fields:
                        # 排除代码字段本身，检查名称字段是否为列表类型且索引有效
                        if name_field != code_field and isinstance(raw[name_field], list) and i < len(raw[name_field]):
                            plate["name"] = raw[name_field][i]
                    # 将板块信息添加到结果列表
                    concept_plates.append(plate)
        
        # 策略2：如果策略1没有找到数据，尝试解析 HQ_StockInfo 分组
        if not concept_plates:
            # 检查响应中是否包含 HQ_StockInfo 分组
            if "HQ_StockInfo" in raw and isinstance(raw["HQ_StockInfo"], list):
                # 遍历 HQ_StockInfo 中的每个项目
                for item in raw["HQ_StockInfo"]:
                    # 检查项目是否为字典类型，且包含与板块相关的键（不区分大小写）
                    if isinstance(item, dict) and any("block" in k.lower() or "concept" in k.lower() for k in item.keys()):
                        concept_plates.append(item)
        
        self.logger.info(f"Fetched {len(concept_plates)} concept plates for stock {code}")
        return concept_plates
