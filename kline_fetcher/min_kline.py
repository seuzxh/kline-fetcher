#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分钟K线获取：1min / 5min / 15min / 30min / 60min。

继承 KLineFetcher 获得 _request / _build_params / _parse_kline_items 等底座，
本类专注分钟K特有的：freq→klinetype 映射、locator 翻页、starttime 定位切片。
"""

import math
from typing import Dict, List, Optional

from kline_fetcher._base import KLineFetcher, KLINE_TYPE_MAP, KLINE_RESPONSE_KEY_MAP

__all__ = ["MinKLineFetcher"]


class MinKLineFetcher(KLineFetcher):
    """分钟K线获取客户端。

    相较基类 KLineFetcher（日K），本类提供分钟频率特有的能力：
      - fetch_min_kline：按 freq 获取分钟K线，支持 locator 自动翻页、去重排序
      - fetch_kline：按 starttime 定位、count 向前/向后切片（实际为分钟K专用）

    使用示例:
        >>> fetcher = MinKLineFetcher()
        >>> data = fetcher.fetch_min_kline("600519", freq="5min", count=-500)
    """

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

            return self._parse_kline_items(data_list[0], klinetype)

        all_data = []
        locator = None

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

            parsed = self._parse_kline_items(data_list[0], klinetype)
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
        """按 starttime 定位、count 向前/向后取分钟K线切片。

        注意：本方法为**分钟K专用**。starttime 格式为 'yyyy-mm-dd HH:mm'（分钟级精度），
        内部调用 fetch_min_kline 并依赖每条数据的 'time' 字段做定位切片，
        因此传入 freq="day" 会因日K数据无 'time' 字段而抛 KeyError。

        参数:
            code: 股票代码，如 "600519"
            freq: 分钟频率，如 "1min"/"5min"/"15min"/"30min"/"60min"
            starttime: 起始时间，格式 'yyyy-mm-dd HH:mm'
            count: 条数。>=0 表示从 starttime 向后取 count 条；<0 表示向前取 |count| 条
            market: 市场代码，None 则自动推断
            adjust: 复权方式 (qfq/hfq/none)，None 用配置默认值

        返回值:
            K线数据列表（按时间升序），定位失败或无数据返回 None。
        """
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
