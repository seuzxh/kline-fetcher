#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分钟K线获取：1min / 5min / 15min / 30min / 60min。

继承 KLineFetcher 获得 _request / _build_params / _parse_kline_items 等底座，
本类专注分钟K特有的：freq→klinetype 映射、locator 翻页、starttime 定位切片。
"""

from typing import Dict, List, Optional

from kline_fetcher._base import KLineFetcher, KLINE_TYPE_MAP, KLINE_RESPONSE_KEY_MAP

__all__ = ["MinKLineFetcher"]


class MinKLineFetcher(KLineFetcher):
    """分钟K线获取客户端。

    相较基类 KLineFetcher（日K），本类提供分钟频率特有的能力：
      - fetch_min_kline：按 freq 获取分钟K线，支持 locator 自动翻页、去重排序

    返回数据自带 date/time 字段，客户端可自行按时间切片，无需专门的时间定位方法。

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

