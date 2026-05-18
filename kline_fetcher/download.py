#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import os
import sys
import time
from typing import Optional

from kline_fetcher.fetcher import KLineFetcher
from kline_fetcher.converter import KLineToQlib

POOL_MAP = {
    "all": "all.txt",
    "csi300": "csi300.txt",
    "csi500": "csi500.txt",
    "csi800": "csi800.txt",
    "csi1000": "csi1000.txt",
    "csiall": "csiall.txt",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("kline_fetcher.download")


PREFIX_TO_MARKET = {
    "sh": 1,
    "sz": 0,
    "bj": 103,
}


def load_stock_pool(pool_name: str, instruments_dir: Optional[str] = None) -> list:
    if instruments_dir is None:
        converter = KLineToQlib()
        instruments_dir = converter.instruments_dir

    filename = POOL_MAP.get(pool_name, pool_name if pool_name.endswith(".txt") else f"{pool_name}.txt")
    filepath = os.path.join(instruments_dir, filename)

    if not os.path.exists(filepath):
        logger.error(f"股池文件不存在: {filepath}")
        return []

    stocks = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            inst_code = parts[0]
            prefix = inst_code[:2].lower()
            code_num = inst_code[2:]
            market = PREFIX_TO_MARKET.get(prefix)
            if market is not None:
                stocks.append((code_num, market, inst_code.lower()))
    return stocks


def download_day_kline(start: str, end: str, pool: str, incremental: bool = True, qlib_data_dir: Optional[str] = None):
    fetcher = KLineFetcher()
    converter = KLineToQlib(qlib_data_dir=qlib_data_dir)

    logger.info(f"日K数据下载: {start} ~ {end}, 股池={pool}, 增量={incremental}")

    stocks = load_stock_pool(pool, instruments_dir=converter.instruments_dir)
    if not stocks:
        raise RuntimeError(f"无法加载股池: {pool}")

    logger.info(f"股池 [{pool}]: {len(stocks)} 只")
    os.makedirs(converter.features_dir, exist_ok=True)

    start_idx = converter.date_to_idx.get(start)
    end_idx = converter.date_to_idx.get(end)
    if start_idx is None:
        for d in converter.dates:
            if d >= start:
                start_idx = converter.date_to_idx[d]
                break
    if end_idx is None:
        for d in reversed(converter.dates):
            if d <= end:
                end_idx = converter.date_to_idx[d]
                break

    total_bars = end_idx - start_idx + 1 if start_idx is not None and end_idx is not None else 0

    segments = []
    if total_bars > 1500:
        seg_start_idx = start_idx
        while seg_start_idx <= end_idx:
            seg_end_idx = min(seg_start_idx + 1499, end_idx)
            seg_start_date = converter.dates[seg_start_idx]
            seg_end_date = converter.dates[seg_end_idx]
            segments.append((seg_start_date, seg_end_date, seg_start_idx, seg_end_idx))
            seg_start_idx = seg_end_idx + 1
        logger.info(f"日K日期范围 {total_bars} 条 > 1500，分为 {len(segments)} 段下载")
    else:
        segments.append((start, end, start_idx, end_idx))

    status = {}
    total = len(stocks)
    success = 0
    failed = 0
    skipped = 0

    for i, (code, market, qlib_dir) in enumerate(stocks):
        if incremental:
            local_start, local_end = converter.check_local_coverage(code, qlib_dir=qlib_dir)
            if local_start is not None and local_end is not None:
                if local_start <= start_idx and local_end >= end_idx:
                    status[code] = "up_to_date"
                    skipped += 1
                    continue

        all_kline = []
        has_error = False
        for seg_start, seg_end, seg_start_idx, seg_end_idx in segments:
            if incremental:
                local_start, local_end = converter.check_local_coverage(code, qlib_dir=qlib_dir)
                if local_start is not None and local_end is not None:
                    if local_start <= seg_start_idx and local_end >= seg_end_idx:
                        continue

            begindate = seg_start.replace("-", "")
            enddate = seg_end.replace("-", "")
            kline_data = fetcher.fetch_day_kline(code, market=market, begindate=begindate, enddate=enddate)
            if kline_data is None:
                has_error = True
                break
            filtered = [d for d in kline_data if seg_start <= d["date"] <= seg_end]
            all_kline.extend(filtered)

        if has_error:
            status[code] = "download_failed"
            failed += 1
            continue

        if not all_kline:
            status[code] = "up_to_date"
            skipped += 1
            continue

        mode = "append" if incremental else "overwrite"
        ok = converter.day_kline_to_qlib(code, all_kline, mode=mode, qlib_dir=qlib_dir)
        if ok:
            status[code] = "downloaded"
            success += 1
        else:
            status[code] = "write_failed"
            failed += 1

        if (i + 1) % 100 == 0:
            logger.info(f"  进度: {i + 1}/{total} (成功={success}, 失败={failed}, 跳过={skipped})")

        time.sleep(0.05)

    logger.info(f"日K数据下载完成: 成功={success}, 失败={failed}, 跳过={skipped}, 总计={total}")
    return status


def download_min_kline(start: str, end: str, pool: str, freq: str = "1min", incremental: bool = True, pages: int = 1, qlib_data_dir: Optional[str] = None):
    fetcher = KLineFetcher()
    converter = KLineToQlib(qlib_data_dir=qlib_data_dir)

    if freq not in converter.min_cal_to_idx or not converter.min_cal_to_idx[freq]:
        logger.error(f"无 {freq} 分钟日历，请先生成日历文件")
        return {}

    logger.info(f"{freq} K线数据下载: {start} ~ {end}, 股池={pool}, 增量={incremental}, 翻页={pages}")

    stocks = load_stock_pool(pool, instruments_dir=converter.instruments_dir)
    if not stocks:
        raise RuntimeError(f"无法加载股池: {pool}")

    logger.info(f"股池 [{pool}]: {len(stocks)} 只")
    os.makedirs(converter.features_dir, exist_ok=True)

    cal_idx_map = converter.min_cal_to_idx[freq]
    cal_timestamps = converter.min_calendars[freq]

    start_ts_prefix = start
    end_ts_prefix = end

    if pages <= 1:
        bars_per_page = {"1min": 240, "5min": 48, "15min": 16, "30min": 8, "60min": 4}
        bpd = bars_per_page.get(freq, 48)
        trading_days_per_page = 1500 // bpd

        start_idx_ts = None
        end_idx_ts = None
        for ts_idx, ts in enumerate(cal_timestamps):
            if ts.startswith(start_ts_prefix) and start_idx_ts is None:
                start_idx_ts = ts_idx
            if ts.startswith(end_ts_prefix):
                end_idx_ts = ts_idx

        if start_idx_ts is not None and end_idx_ts is not None:
            needed_bars = end_idx_ts - start_idx_ts + 1
            needed_days = needed_bars / bpd
            pages = max(1, int(needed_days / trading_days_per_page) + 1)
            logger.info(f"{freq} 日期范围需约 {needed_days:.0f} 个交易日，自动计算翻页 {pages} 次")

    status = {}
    total = len(stocks)
    success = 0
    failed = 0
    skipped = 0

    for i, (code, market, qlib_dir) in enumerate(stocks):
        if incremental:
            local_start, local_end = converter.check_local_coverage(code, freq=freq, qlib_dir=qlib_dir)
            if local_start is not None and local_end is not None:
                if local_end < len(cal_timestamps):
                    last_ts = cal_timestamps[local_end]
                    if last_ts.startswith(end_ts_prefix):
                        status[code] = "up_to_date"
                        skipped += 1
                        continue

        count = -1500
        kline_data = fetcher.fetch_min_kline(code, freq=freq, count=count, market=market, pages=pages)
        if kline_data is None:
            status[code] = "download_failed"
            failed += 1
            continue

        filtered = [d for d in kline_data if start <= d["date"] <= end]
        if not filtered:
            status[code] = "no_data_in_range"
            skipped += 1
            continue

        mode = "append" if incremental else "overwrite"
        ok = converter.min_kline_to_qlib(code, filtered, freq=freq, mode=mode, qlib_dir=qlib_dir)
        if ok:
            status[code] = "downloaded"
            success += 1
        else:
            status[code] = "write_failed"
            failed += 1

        if (i + 1) % 50 == 0:
            logger.info(f"  进度: {i + 1}/{total} (成功={success}, 失败={failed}, 跳过={skipped})")

        time.sleep(0.05)

    logger.info(f"{freq} K线数据下载完成: 成功={success}, 失败={failed}, 跳过={skipped}, 总计={total}")
    return status


def main():
    parser = argparse.ArgumentParser(description="从 KLine API 下载行情数据到 qlib_data/")
    parser.add_argument("--start", required=True, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--pool", default="all", help="股池名称 (all/csi300/csi500/csi800/csi1000/csiall)")
    parser.add_argument("--full", action="store_true", help="强制全量下载（默认增量更新）")
    parser.add_argument("--freq", default="day", choices=["day", "1min", "5min"], help="数据频率")
    parser.add_argument("--pages", type=int, default=0, help="高频数据翻页次数（0=自动计算）")
    parser.add_argument("--qlib-data-dir", default=None, help="qlib 数据目录路径")
    args = parser.parse_args()

    if args.freq == "day":
        download_day_kline(args.start, args.end, args.pool, incremental=not args.full, qlib_data_dir=args.qlib_data_dir)
    elif args.freq in ("1min", "5min"):
        pages = args.pages if args.pages > 0 else 1
        download_min_kline(args.start, args.end, args.pool, freq=args.freq, incremental=not args.full, pages=pages, qlib_data_dir=args.qlib_data_dir)
    else:
        logger.error(f"暂不支持频率: {args.freq}")
        sys.exit(1)


if __name__ == "__main__":
    main()
