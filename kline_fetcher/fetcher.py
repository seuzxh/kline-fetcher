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

        numeric_code = code.lstrip("SHshSZszBJbj") or code

        params = {
            "Action": 10002,
            "code": numeric_code,
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
        # 构建请求参数
        params = {
            "Action": 10007,  # 接口动作代码，10007表示获取概念板块列表
            "TFrom": "newAndroid",
            "needtitle": 1,
            "subtype": 1,
            "rights": 0,
            "uniqueid": "5BE160A5-E1D9-3DF2-B24D-337FE097D3C2",
            "direction": 1,
            "clientversion": "6.2.8",
            "906.props": "0|2|10|514",
            "__SDK_VER": 1,
            "start": 0,  # 分页起始位置
            "count": 30,  # 每页数量
            "groups": "HQ_StockInfo|HQ_StockProp",
            "mobilekind": "android_Xiaomi_11",
            "sort": 514,  # 排序字段，514表示涨跌幅
            "CFrom": "GXAPP",
            "props": "10|510|514|573|4|575|5|574|6|576|7|577|12|13|21|551|513|521|23|906|751|752|753|754|755|756|757|11",
            "market": 44,  # 市场代码，44表示概念板块市场
            "Route": 1,
            "routemarkets": 44,
            "langtype": 1,
            "deviceName": "Xiaomi",
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
        klinetype = "500"
        params = {
            "Action": 10002,
            "code": plate_code,
            "market": market,
            "klinetype": klinetype,
            "cqType": 0,
            "props": "0|1|2|3|4|191|190|422|519",
            "422.daycount": -220,
            f"{klinetype}.count": count,
            "TFrom": "newAndroid",
            "CFrom": "GXAPP",
            "clientversion": "6.2.8",
            "__SDK_VER": 1,
            "mobilekind": "android_Xiaomi_11",
            "uniqueid": "5BE160A5-E1D9-3DF2-B24D-337FE097D3C2",
            "Route": 1,
            "langtype": 1,
            "deviceName": "Xiaomi",
        }

        raw = self._request(params)
        if raw is None:
            return None

        response_key = KLINE_RESPONSE_KEY_MAP.get(klinetype)
        if not response_key or response_key not in raw:
            self.logger.warning(f"No {response_key} in response for plate_code={plate_code}")
            return None

        data_list = raw[response_key]
        if not data_list or len(data_list) == 0:
            self.logger.warning(f"Empty {response_key} for plate_code={plate_code}")
            return None

        stocks_per_h = raw.get("StocksPerH", 100)
        if isinstance(stocks_per_h, list) and stocks_per_h:
            stocks_per_h = stocks_per_h[0]
        stocks_per_h = int(stocks_per_h) if stocks_per_h else 100

        return self._parse_kline_items(data_list[0], klinetype, stocks_per_h)

    def get_concept_plate_stocks(self, plate_code: str, start: int = 0, count: int = 10) -> Optional[List[Dict]]:
        params = {
            "Action": 10005,
            "block.include": 1,
            "block.type": 1,
            "TFrom": "newAndroid",
            "needtitle": 1,
            "rights": 0,
            "block": plate_code,
            "uniqueid": "5BE160A5-E1D9-3DF2-B24D-337FE097D3C2",
            "direction": 1,
            "clientversion": "6.2.8",
            "__SDK_VER": 1,
            "start": start,
            "count": count,
            "groups": "HQ_StockInfo|HQ_StockProp",
            "mobilekind": "android_Xiaomi_11",
            "sort": 514,
            "CFrom": "GXAPP",
            "props": "710|560|514|10|4|6|7|60|61|62|11|510|711",
            "Route": 1,
            "routemarkets": 44,
            "langtype": 1,
            "deviceName": "Xiaomi",
        }

        raw = self._request(params)
        if raw is None:
            return None

        # 解析成份股数据
        stocks = []
        if "StockCode" in raw and "StockName" in raw and "MarketSN" in raw:
            codes = raw["StockCode"]
            names = raw["StockName"]
            markets = raw["MarketSN"]
            
            for i in range(len(codes)):
                stock = {
                    "code": codes[i],
                    "name": names[i],
                    "market": markets[i]
                }
                # 添加其他可能的字段
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
        params = {
            "Action": 10000,
            "codes": f"{code}|{market}",
            "clientversion": "6.2.8",
            "__sdk_ver": 10001,
            "count": 1,
            "groups": "HQ_StockInfo",
            "mobilekind": "android_Xiaomi_11",
            "TFrom": "newAndroid",
            "tztreqfrom": "android.webview",
            "CFrom": "GXAPP",
            "props": "11|10|147|19|20|13|521|22|23|320|554|555|1034|553|1001|550|1040|552|1033|124|125|135|134|104|105|141|142|289|422|131|132|133|190|191|1039|1|",
            "market": market,
            "reqlinktype": 0,
            "tztsno": "de6fb0a5c07461e3212220fbb33b8a1c",
            "langtype": 1,
            "deviceName": "Xiaomi",
            "outtype": 1,
            "uniqueid": "5BE160A5-E1D9-3DF2-B24D-337FE097D3C2",
        }

        raw = self._request(params)
        if raw is None:
            return None

        # 解析股票所属概念板块数据
        # 注意：这个API的响应格式可能与其他不同，需要根据实际情况调整
        concept_plates = []
        
        # 检查是否有概念板块相关的字段
        # 可能的字段名：BlockCode, BlockName, ConceptCode, ConceptName 等
        # 这里使用一个更通用的方式，检查所有可能包含概念板块信息的字段
        
        # 先尝试查找包含板块信息的字段
        block_fields = []
        for key in raw.keys():
            if "Block" in key or "Concept" in key:
                block_fields.append(key)
        
        if block_fields:
            # 假设第一个板块字段包含概念板块代码
            code_field = block_fields[0]
            if isinstance(raw[code_field], list):
                for i, plate_code in enumerate(raw[code_field]):
                    plate = {
                        "code": plate_code
                    }
                    # 尝试查找对应的名称字段
                    for name_field in block_fields:
                        if name_field != code_field and isinstance(raw[name_field], list) and i < len(raw[name_field]):
                            plate["name"] = raw[name_field][i]
                    concept_plates.append(plate)
        
        if not concept_plates:
            # 如果没有找到明确的板块字段，尝试解析HQ_StockInfo
            if "HQ_StockInfo" in raw and isinstance(raw["HQ_StockInfo"], list):
                for item in raw["HQ_StockInfo"]:
                    if isinstance(item, dict) and any("block" in k.lower() or "concept" in k.lower() for k in item.keys()):
                        concept_plates.append(item)
        
        self.logger.info(f"Fetched {len(concept_plates)} concept plates for stock {code}")
        return concept_plates
