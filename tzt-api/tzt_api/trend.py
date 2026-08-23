#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分时数据获取：当日分时、历史分时。

继承 KLineFetcher 获得 _request / infer_market 等底座，
本类专注分时数据特有的：Action=10001、trendtypes=-1、date/daycount 参数构造。
"""

from typing import Dict, List, Optional

from tzt_api._base import KLineFetcher, PRICE_SCALE, TURNOVER_SCALE

__all__ = ["TrendFetcher"]


class TrendFetcher(KLineFetcher):
    """分时数据获取客户端。

    提供分时数据获取能力：
      - fetch_intraday_trend：获取当日分时数据
      - fetch_history_trend：获取历史分时数据

    使用示例:
        >>> fetcher = TrendFetcher()
        >>> # 当日分时
        >>> data = fetcher.fetch_intraday_trend("600519")
        >>> # 历史分时
        >>> data = fetcher.fetch_history_trend("600519", "20260611")
    """

    def _build_trend_params(self, code: str, date: int, daycount: int, market: Optional[int] = None) -> Dict:
        """构造分时数据请求参数"""
        if market is None:
            market = self.infer_market(code)
        
        numeric_code = code.lstrip("SHshSZszBJbj") or code
        
        params = {
            "Action": 10001,
            "code": numeric_code,
            "market": market,
            "trendtypes": -1,
            "date": date,
            "daycount": daycount,
            "421.date": date,
            "421.daycount": daycount,
            "422.date": date,
            "422.daycount": daycount,
            "423.date": date,
            "423.daycount": daycount,
        }
        
        return params

    def _convert_trend_time(self, time_raw: int) -> Dict[str, str]:
        """转换时间戳为日期和时间"""
        time_str = str(time_raw).zfill(14)
        if len(time_str) != 14:
            return {"date": "", "time": ""}
        date = f"{time_str[0:4]}-{time_str[4:6]}-{time_str[6:8]}"
        time = f"{time_str[8:10]}:{time_str[10:12]}:{time_str[12:14]}"
        return {"date": date, "time": time}

    def _parse_call_trend(self, data_list: list) -> List[Dict]:
        """解析盘前数据（CallTrend）"""
        result = []
        for item in data_list:
            if not isinstance(item, dict):
                continue
            dt = self._convert_trend_time(item.get("Time", 0))
            if not dt["date"]:
                continue
            
            row = {
                "date": dt["date"],
                "time": dt["time"],
                "ref_price": self._convert_price(item.get("RefPrice", 0)),
                "matched_vol": self._convert_volume(item.get("MatchedVol", 0)),
                "non_matched_vol_buy": self._convert_volume(item.get("NonMatchedVolBuy", 0)),
                "non_matched_vol_sell": self._convert_volume(item.get("NonMatchedVolSell", 0)),
                "phase": "pre-market",
            }
            result.append(row)
        return result

    def _parse_trend_op(self, data_list: list) -> List[Dict]:
        """解析盘中数据（TrendOp）"""
        result = []
        for item in data_list:
            if not isinstance(item, dict):
                continue
            dt = self._convert_trend_time(item.get("Time", 0))
            if not dt["date"]:
                continue
            
            row = {
                "date": dt["date"],
                "time": dt["time"],
                "last_price": self._convert_price(item.get("LastPrice", 0)),
                "avg_price": self._convert_price(item.get("AvgPrice", 0)),
                "volume": self._convert_volume(item.get("Volume", 0)),
                "turnover": self._convert_turnover(item.get("Turnover", 0)),
                "phase": "trading",
            }
            result.append(row)
        return result

    def fetch_intraday_trend(self, code: str, market: Optional[int] = None) -> Optional[Dict[str, List[Dict]]]:
        """获取当日分时数据（date=0, daycount=0）
        
        Args:
            code: 股票代码，支持 "600519", "SH600519" 等格式
            market: 市场代码，可选，自动推断
        
        Returns:
            Dict 包含:
                - pre_market: 盘前数据列表
                - trading: 盘中数据列表
                - market_date: 市场日期
        """
        params = self._build_trend_params(code, date=0, daycount=0, market=market)
        self.logger.info(f"Fetching intraday trend: code={code}, market={params['market']}")
        
        raw = self._request(params)
        if raw is None:
            return None
        
        error_no = raw.get("ErrorNo")
        if error_no and str(error_no) != "0":
            self.logger.warning(f"API error: {raw.get('ErrorMessage', 'unknown')}")
            return None
        
        result = {
            "market_date": raw.get("marketdate", ""),
            "pre_market": [],
            "trading": [],
        }
        
        call_trend = raw.get("CallTrend")
        if call_trend and isinstance(call_trend, list) and len(call_trend) > 0:
            result["pre_market"] = self._parse_call_trend(call_trend[0])
        
        trend_op = raw.get("TrendOp")
        if trend_op and isinstance(trend_op, list) and len(trend_op) > 0:
            result["trading"] = self._parse_trend_op(trend_op[0])
        
        if not result["pre_market"] and not result["trading"]:
            self.logger.warning(f"Empty trend data for code={code}")
            return None
        
        return result

    def fetch_history_trend(self, code: str, date: str, market: Optional[int] = None) -> Optional[Dict[str, List[Dict]]]:
        """获取历史分时数据（date指定日期, daycount=1）
        
        Args:
            code: 股票代码，支持 "600519", "SH600519" 等格式
            date: 历史日期，格式 "YYYYMMDD"
            market: 市场代码，可选，自动推断
        
        Returns:
            Dict 包含:
                - pre_market: 盘前数据列表
                - trading: 盘中数据列表
                - market_date: 市场日期
        """
        try:
            date_int = int(date)
        except (ValueError, TypeError):
            self.logger.error(f"Invalid date format: {date}, expected YYYYMMDD")
            return None
        
        params = self._build_trend_params(code, date=date_int, daycount=1, market=market)
        self.logger.info(f"Fetching history trend: code={code}, date={date}, market={params['market']}")
        
        raw = self._request(params)
        if raw is None:
            return None
        
        error_no = raw.get("ErrorNo")
        if error_no and str(error_no) != "0":
            self.logger.warning(f"API error: {raw.get('ErrorMessage', 'unknown')}")
            return None
        
        result = {
            "market_date": raw.get("marketdate", ""),
            "pre_market": [],
            "trading": [],
        }
        
        call_trend = raw.get("CallTrend")
        if call_trend and isinstance(call_trend, list) and len(call_trend) > 0:
            result["pre_market"] = self._parse_call_trend(call_trend[0])
        
        trend_op = raw.get("TrendOp")
        if trend_op and isinstance(trend_op, list) and len(trend_op) > 0:
            result["trading"] = self._parse_trend_op(trend_op[0])
        
        if not result["pre_market"] and not result["trading"]:
            self.logger.warning(f"Empty history trend data for code={code}, date={date}")
            return None
        
        return result

    def fetch_trend(self, code: str, date: Optional[str] = None, market: Optional[int] = None) -> Optional[Dict[str, List[Dict]]]:
        """获取分时数据（自动判断当日或历史）
        
        Args:
            code: 股票代码，支持 "600519", "SH600519" 等格式
            date: 日期，格式 "YYYYMMDD"，为None或"0"时获取当日数据
            market: 市场代码，可选，自动推断
        
        Returns:
            Dict 包含:
                - pre_market: 盘前数据列表
                - trading: 盘中数据列表
                - market_date: 市场日期
        """
        if date is None or date == "0":
            return self.fetch_intraday_trend(code, market=market)
        return self.fetch_history_trend(code, date, market=market)
