#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""概念板块相关请求：板块列表、板块K线、板块成份股、股票所属板块。

继承 KLineFetcher 获得 _request 等底座。概念板块方法既非纯日K也非纯分钟K，
独立成模块以便后续演进（如板块成份股分页、所属板块多策略解析等）。
"""

from typing import Dict, List, Optional

from kline_fetcher._base import KLineFetcher, KLINE_RESPONSE_KEY_MAP

__all__ = ["ConceptPlateFetcher"]


class ConceptPlateFetcher(KLineFetcher):
    """概念板块数据获取客户端。

    提供中焯行情 API 的概念板块相关接口封装：
      - get_all_concept_plates：获取所有概念板块列表
      - get_concept_plate_kline：获取指定板块的日K线
      - get_concept_plate_stocks：获取板块成份股（分页）
      - get_stock_concept_plates：获取股票所属的概念板块

    使用示例:
        >>> fetcher = ConceptPlateFetcher()
        >>> plates = fetcher.get_all_concept_plates()
    """

    def get_all_concept_plates(self) -> Optional[List[Dict]]:
        """获取所有概念板块列表。

        从API获取A股所有概念板块的基本信息，包括板块代码、名称、市场代码以及
        可能的行情数据（最新价、涨跌额、涨跌幅）。

        返回值:
            Optional[List[Dict]]: 概念板块列表，每个板块是一个字典，包含以下键：
                - code (str): 板块代码
                - name (str): 板块名称
                - market (int): 市场代码（44表示概念板块市场）
                - price (int, optional): 最新价（原始整数格式）
                - change (int, optional): 涨跌额（原始整数格式）
                - change_pct (int, optional): 涨跌幅（原始整数格式）
            如果请求失败，返回 None。
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

        raw = self._request(params)
        if raw is None:
            return None

        plates = []

        if "StockCode" in raw and "StockName" in raw and "MarketSN" in raw:
            codes = raw["StockCode"]
            names = raw["StockName"]
            markets = raw["MarketSN"]

            for i in range(len(codes)):
                plate = {
                    "code": codes[i],
                    "name": names[i],
                    "market": markets[i]
                }

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

        从API获取指定概念板块的历史日K线数据。默认获取最近220个交易日的数据。

        参数:
            plate_code (str): 概念板块代码，例如 "994612"
            count (int, optional): K线数量，负值表示从最新数据向前获取。
                默认值为 -220。
            market (int, optional): 市场代码，44表示概念板块市场。默认值为 44。

        返回值:
            Optional[List[Dict]]: K线数据列表。如果请求失败或无数据，返回 None。
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

        return self._parse_kline_items(data_list[0], klinetype)

    def get_concept_plate_stocks(self, plate_code: str, start: int = 0, count: int = 10) -> Optional[List[Dict]]:
        """获取指定概念板块的成份股列表。

        参数:
            plate_code (str): 概念板块代码，例如 "994612"
            start (int, optional): 分页起始位置，从 0 开始。默认值为 0。
            count (int, optional): 每页获取的股票数量。默认值为 10。

        返回值:
            Optional[List[Dict]]: 成份股列表，每个股票包含 code/name/market
            及可选的 price/change/change_pct/high/low。请求失败返回 None。
        """
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

        raw = self._request(params)
        if raw is None:
            return None

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

        参数:
            code (str): 股票代码，例如 "600519"
            market (int): 市场代码，0表示深圳，1表示上海，103表示北京

        返回值:
            Optional[List[Dict]]: 概念板块列表，每个板块包含 code 及可选的 name。
            请求失败返回 None。
        """
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

        raw = self._request(params)
        if raw is None:
            return None

        concept_plates = []

        # 策略1：查找包含 "Block" 或 "Concept" 关键词的字段
        block_fields = []
        for key in raw.keys():
            if "Block" in key or "Concept" in key:
                block_fields.append(key)

        if block_fields:
            code_field = block_fields[0]
            if isinstance(raw[code_field], list):
                for i, plate_code in enumerate(raw[code_field]):
                    plate = {
                        "code": plate_code
                    }
                    for name_field in block_fields:
                        if name_field != code_field and isinstance(raw[name_field], list) and i < len(raw[name_field]):
                            plate["name"] = raw[name_field][i]
                    concept_plates.append(plate)

        # 策略2：如果策略1没有找到数据，尝试解析 HQ_StockInfo 分组
        if not concept_plates:
            if "HQ_StockInfo" in raw and isinstance(raw["HQ_StockInfo"], list):
                for item in raw["HQ_StockInfo"]:
                    if isinstance(item, dict) and any("block" in k.lower() or "concept" in k.lower() for k in item.keys()):
                        concept_plates.append(item)

        self.logger.info(f"Fetched {len(concept_plates)} concept plates for stock {code}")
        return concept_plates
