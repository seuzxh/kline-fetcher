#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""概念板块相关请求：板块列表、板块K线、板块成份股、股票所属板块。

继承 KLineFetcher 获得 _request 等底座。概念板块方法既非纯日K也非纯分钟K，
独立成模块以便后续演进（如板块成份股分页、所属板块多策略解析等）。
"""

from typing import Dict, List, Optional

from tzt_api._base import KLineFetcher, KLINE_RESPONSE_KEY_MAP

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

    # 股票所属板块的关联属性 ID（《行情3.0股票属性ID》v1.229）：
    #   900 = CoIndBlkIdx 隶属行业板块指数（仅 1 条）
    #   901 = CoBlkIdx 隶属版块指数（含行业/概念/地域/风格，可多条）
    #   923 = RegionBlkIdx 地域板块
    # 关联属性（val_type=8）须配 {propID}.props 指定关联证券的出参属性：0=代码 1=市场 2=名称
    STOCK_PLATE_PROPS = "900|901|923"
    PLATE_RESPONSE_KEYS = {
        "900": "CoIndBlkIdx",
        "901": "CoBlkIdx",
        "923": "RegionBlkIdx",
    }

    @staticmethod
    def _parse_plate_group(raw: Dict, key: str) -> List[Dict]:
        """解析 10000 响应中单个板块属性的关联证券列表。

        响应结构（outtype=1）: {key: [{"StockCode": [...], "StockName": [...], "MarketSN": [...]}]}
        """
        group = raw.get(key)
        if not group or not isinstance(group, list) or len(group) == 0:
            return []
        inner = group[0]
        if not isinstance(inner, dict):
            return []

        codes = inner.get("StockCode") or []
        names = inner.get("StockName") or []
        markets = inner.get("MarketSN") or []

        plates = []
        for i, plate_code in enumerate(codes):
            plate = {"code": plate_code}
            if i < len(names):
                plate["name"] = names[i]
            if i < len(markets):
                plate["market"] = markets[i]
            plates.append(plate)
        return plates

    def get_stock_concept_plates(self, code: str, market: Optional[int] = None, plate_type: Optional[str] = None) -> Optional[List[Dict]]:
        """获取指定股票所属的板块列表（官方属性 901 CoBlkIdx，2026-08 实测可用）。

        通过 Action=10000 请求关联属性 900（行业）/901（全部）/923（地域），
        用 900/923 的结果给 901 的板块标注类型。

        参数:
            code (str): 股票代码，例如 "600519"。裸码按指数优先规则推断市场，
                深市 000xxx 个股请用 "sz000001" 或显式传 market。
            market (int, optional): 市场代码，0深圳 1上海 103北京。默认自动推断。
            plate_type (str, optional): 板块类型过滤，可选 "industry"（行业）/
                "region"（地域）/"concept"（概念及风格）。默认 None 返回全部并带 type 字段。

        返回值:
            Optional[List[Dict]]: 板块列表，每项 {"code", "name", "market", "type"}。
            请求失败返回 None，无板块数据返回 []。
        """
        if market is None:
            market = self.infer_market(code)
        numeric_code = self._numeric_code(code)

        params = {
            "Action": 10000,
            "codes": f"{numeric_code}|{market}",
            "count": 1,
            "props": self.STOCK_PLATE_PROPS,
            "market": market,
            "outtype": 1,
        }
        for prop_id in self.STOCK_PLATE_PROPS.split("|"):
            params[f"{prop_id}.props"] = "0|1|2"

        raw = self._request(params)
        if raw is None:
            return None

        industry = self._parse_plate_group(raw, self.PLATE_RESPONSE_KEYS["900"])
        region = self._parse_plate_group(raw, self.PLATE_RESPONSE_KEYS["923"])
        all_plates = self._parse_plate_group(raw, self.PLATE_RESPONSE_KEYS["901"])
        if not all_plates:
            # CoBlkIdx 缺失时退化为行业+地域并集（正常沪深京股票不会走到这里）
            all_plates = industry + region

        industry_codes = {p["code"] for p in industry}
        region_codes = {p["code"] for p in region}
        for plate in all_plates:
            if plate["code"] in industry_codes:
                plate["type"] = "industry"
            elif plate["code"] in region_codes:
                plate["type"] = "region"
            else:
                plate["type"] = "concept"

        if plate_type is not None:
            plate_type = plate_type.lower()
            if plate_type not in ("industry", "region", "concept"):
                raise ValueError(f"无效的 plate_type: {plate_type}，可选值: industry, region, concept")
            all_plates = [p for p in all_plates if p["type"] == plate_type]

        self.logger.info(f"Fetched {len(all_plates)} plates for stock {code} (plate_type={plate_type})")
        return all_plates
