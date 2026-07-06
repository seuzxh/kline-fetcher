#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KLineToQlib：K线数据转换为 qlib bin 格式。

管理交易日历（日/分钟）、bin 文件读写、增量追加（_append_bin）。
"""
import logging
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

_DEFAULT_QLIB_DATA_DIR = os.environ.get(
    "QLIB_DATA_DIR",
    "/root/Projects/0.qlib_pro/qlib_data",
)

QLIB_DAY_FIELDS = ["open", "high", "low", "close", "volume", "factor", "vwap"]
QLIB_MIN_FIELDS = ["open", "high", "low", "close", "volume", "factor", "vwap"]


class KLineToQlib:
    def __init__(self, qlib_data_dir: Optional[str] = None):
        self.qlib_data_dir = qlib_data_dir or _DEFAULT_QLIB_DATA_DIR
        self.features_dir = os.path.join(self.qlib_data_dir, "features")
        self.calendar_file = os.path.join(self.qlib_data_dir, "calendars", "day.txt")
        self.instruments_dir = os.path.join(self.qlib_data_dir, "instruments")
        self.min_calendar_files = {
            "1min": os.path.join(self.qlib_data_dir, "calendars", "1min.txt"),
            "5min": os.path.join(self.qlib_data_dir, "calendars", "5min.txt"),
        }

        self.logger = logging.getLogger(self.__class__.__name__)
        self.dates: List[str] = []
        self.date_to_idx: Dict[str, int] = {}
        self.min_calendars: Dict[str, List[str]] = {}
        self.min_cal_to_idx: Dict[str, Dict[str, int]] = {}
        self._load_calendar()
        self._load_min_calendars()

    def _load_calendar(self):
        if os.path.exists(self.calendar_file):
            with open(self.calendar_file, "r") as f:
                self.dates = [l.strip() for l in f.readlines() if l.strip()]
        self.date_to_idx = {d: i for i, d in enumerate(self.dates)}
        self.logger.info(f"Loaded {len(self.dates)} trade dates from calendar")

    def _load_min_calendars(self):
        for freq, cal_file in self.min_calendar_files.items():
            if os.path.exists(cal_file):
                with open(cal_file, "r") as f:
                    timestamps = [l.strip() for l in f.readlines() if l.strip()]
                self.min_calendars[freq] = timestamps
                self.min_cal_to_idx[freq] = {ts: i for i, ts in enumerate(timestamps)}
                self.logger.info(f"Loaded {len(timestamps)} {freq} calendar entries")

    def ensure_calendar(self, fetcher=None, start_year: int = 2000, end_year: int = 2030):
        if self.dates:
            self.logger.info(f"Calendar already loaded ({len(self.dates)} dates), skip generation")
            return True

        if fetcher is None:
            from kline_fetcher.fetcher import KLineFetcher
            fetcher = KLineFetcher()

        self.logger.info("No trade calendar found, generating from API...")
        dates = fetcher.fetch_trade_calendar(start_year=start_year, end_year=end_year)
        if not dates:
            self.logger.error("Failed to fetch trade calendar from API")
            return False

        cal_dir = os.path.join(self.qlib_data_dir, "calendars")
        os.makedirs(cal_dir, exist_ok=True)

        with open(self.calendar_file, "w") as f:
            f.write("\n".join(dates) + "\n")

        self.dates = dates
        self.date_to_idx = {d: i for i, d in enumerate(self.dates)}
        self.logger.info(f"Generated and saved {len(dates)} trade dates to {self.calendar_file}")
        return True

    def generate_min_calendar(self, freq: str = "1min"):
        if not self.dates:
            self.logger.error("No day calendar loaded, call ensure_calendar() first")
            return False

        bars_per_day = {"1min": 240, "5min": 48, "15min": 16, "30min": 8, "60min": 4}
        bpd = bars_per_day.get(freq)
        if bpd is None:
            self.logger.error(f"Unsupported freq for calendar generation: {freq}")
            return False

        session_times = {
            "1min": self._generate_1min_timestamps,
            "5min": self._generate_5min_timestamps,
        }
        gen_func = session_times.get(freq, self._generate_generic_min_timestamps)

        timestamps = []
        for date in self.dates:
            day_timestamps = gen_func(date, bpd, freq)
            timestamps.extend(day_timestamps)

        cal_dir = os.path.join(self.qlib_data_dir, "calendars")
        os.makedirs(cal_dir, exist_ok=True)
        cal_file = os.path.join(cal_dir, f"{freq}.txt")

        with open(cal_file, "w") as f:
            f.write("\n".join(timestamps) + "\n")

        self.min_calendars[freq] = timestamps
        self.min_cal_to_idx[freq] = {ts: i for i, ts in enumerate(timestamps)}
        self.min_calendar_files[freq] = cal_file
        self.logger.info(f"Generated and saved {len(timestamps)} {freq} calendar entries to {cal_file}")
        return True

    @staticmethod
    def _generate_1min_timestamps(date: str, bpd: int, freq: str) -> List[str]:
        """生成 1min 日历时间戳（240 条）。

        中焯 API 用「周期结束时刻」标记每根K线：09:31~11:30、13:01~15:00。
        API 不返回 09:30 和 13:00 的数据，日历从 09:31/13:01 起以对齐实际数据。
        保留 11:30（上午收盘）和 15:00（全天收盘）。
        """
        timestamps = []
        # 上午 09:31~11:30
        for h in range(9, 12):
            for m in range(0, 60):
                if h == 9 and m < 31:
                    continue
                if h == 11 and m > 30:
                    continue
                timestamps.append(f"{date} {h:02d}:{m:02d}:00")
        # 下午 13:01~15:00
        for h in range(13, 16):
            for m in range(0, 60):
                if h == 13 and m < 1:
                    continue
                if h == 15 and m > 0:
                    continue
                timestamps.append(f"{date} {h:02d}:{m:02d}:00")
        return timestamps

    @staticmethod
    def _generate_5min_timestamps(date: str, bpd: int, freq: str) -> List[str]:
        """生成 5min 日历时间戳。同 1min 的边界语义：含 11:30 和 15:00。"""
        timestamps = []
        # 上午 09:30~11:30
        for m in range(30, 60, 5):
            timestamps.append(f"{date} 09:{m:02d}:00")
        for m in range(0, 60, 5):
            timestamps.append(f"{date} 10:{m:02d}:00")
        for m in range(0, 31, 5):  # 含 11:30（上午收盘）
            timestamps.append(f"{date} 11:{m:02d}:00")
        # 下午 13:00~15:00
        for m in range(0, 60, 5):
            timestamps.append(f"{date} 13:{m:02d}:00")
        for m in range(0, 60, 5):
            timestamps.append(f"{date} 14:{m:02d}:00")
        timestamps.append(f"{date} 15:00:00")  # 含 15:00（全天收盘）
        return timestamps

    @staticmethod
    def _generate_generic_min_timestamps(date: str, bpd: int, freq: str) -> List[str]:
        freq_minutes = {"1min": 1, "5min": 5, "15min": 15, "30min": 30, "60min": 60}
        step = freq_minutes.get(freq, 5)
        timestamps = []
        morning_start = 9 * 60 + 30
        morning_end = 11 * 60 + 30
        afternoon_start = 13 * 60
        afternoon_end = 15 * 60
        t = morning_start
        while t < morning_end:
            h, m = divmod(t, 60)
            timestamps.append(f"{date} {h:02d}:{m:02d}:00")
            t += step
        t = afternoon_start
        while t <= afternoon_end:
            h, m = divmod(t, 60)
            timestamps.append(f"{date} {h:02d}:{m:02d}:00")
            t += step
        return timestamps

    @staticmethod
    def code_to_qlib_dir(code: str) -> str:
        upper = code.upper()
        if upper.startswith("SH"):
            return f"sh{code.lstrip('SHsh')}"
        if upper.startswith("SZ"):
            return f"sz{code.lstrip('SZsz')}"
        if upper.startswith("BJ"):
            return f"bj{code.lstrip('BJbj')}"
        numeric = code.lstrip("SHshSZszBJbj")
        if numeric.startswith(("600", "601", "603", "605", "688", "689")):
            return f"sh{code}"
        if numeric.startswith(("000", "001", "002", "003", "300", "301")):
            return f"sz{code}"
        if numeric.startswith(("8", "4", "920")):
            return f"bj{code}"
        return f"sz{code}"

    def day_kline_to_qlib(self, code: str, kline_data: List[Dict], mode: str = "append", qlib_dir: Optional[str] = None) -> bool:
        if not kline_data:
            self.logger.warning(f"Empty kline data for {code}")
            return False

        field_arrays = self._build_day_arrays(kline_data)
        if field_arrays is None:
            return False

        qlib_dir = qlib_dir or self.code_to_qlib_dir(code)
        stock_dir = os.path.join(self.features_dir, qlib_dir)
        os.makedirs(stock_dir, exist_ok=True)

        start_idx = field_arrays.pop("_start_idx")

        for field, arr in field_arrays.items():
            bin_path = os.path.join(stock_dir, f"{field}.day.bin")
            if mode == "overwrite" or not os.path.exists(bin_path):
                full_data = np.hstack([np.array([start_idx], dtype="<f"), arr.astype("<f")])
                full_data.tofile(str(bin_path))
            else:
                self._append_bin(bin_path, arr, start_idx)

        self.logger.info(f"Wrote day kline for {code} ({qlib_dir}): {len(kline_data)} bars, start_idx={start_idx}")
        return True

    def min_kline_to_qlib(self, code: str, kline_data: List[Dict], freq: str = "1min", mode: str = "append", qlib_dir: Optional[str] = None) -> bool:
        if not kline_data:
            self.logger.warning(f"Empty min kline data for {code}")
            return False

        if freq not in self.min_cal_to_idx:
            self.logger.error(f"No {freq} calendar loaded, cannot write min kline")
            return False

        field_arrays = self._build_min_arrays(kline_data, freq)
        if field_arrays is None:
            return False

        qlib_dir = qlib_dir or self.code_to_qlib_dir(code)
        stock_dir = os.path.join(self.features_dir, qlib_dir)
        os.makedirs(stock_dir, exist_ok=True)

        start_idx = field_arrays.pop("_start_idx")

        for field, arr in field_arrays.items():
            bin_path = os.path.join(stock_dir, f"{field}.{freq}.bin")
            if mode == "overwrite" or not os.path.exists(bin_path):
                full_data = np.hstack([np.array([start_idx], dtype="<f"), arr.astype("<f")])
                full_data.tofile(str(bin_path))
            else:
                self._append_bin(bin_path, arr, start_idx)

        self.logger.info(f"Wrote {freq} kline for {code} ({qlib_dir}): {len(kline_data)} bars, start_idx={start_idx}")
        return True

    def _build_day_arrays(self, kline_data: List[Dict]) -> Optional[Dict]:
        indices = []
        for item in kline_data:
            idx = self.date_to_idx.get(item["date"])
            indices.append(idx)

        valid_indices = [i for i in indices if i is not None]
        if not valid_indices:
            self.logger.warning("No valid dates in kline data")
            return None

        min_idx = min(valid_indices)
        max_idx = max(valid_indices)
        cal_len = max_idx - min_idx + 1

        field_arrays = {"_start_idx": min_idx}
        for field in QLIB_DAY_FIELDS:
            field_arrays[field] = np.full(cal_len, np.nan, dtype=np.float32)

        for i, (idx, item) in enumerate(zip(indices, kline_data)):
            if idx is None:
                continue
            pos = idx - min_idx
            if 0 <= pos < cal_len:
                for field in ["open", "high", "low", "close", "volume", "factor"]:
                    if field in item:
                        field_arrays[field][pos] = float(item[field])
                if "amount" in item and item.get("volume", 0) > 0:
                    field_arrays["vwap"][pos] = float(item["amount"]) / float(item["volume"])

        return field_arrays

    def _build_min_arrays(self, kline_data: List[Dict], freq: str) -> Optional[Dict]:
        cal_idx_map = self.min_cal_to_idx.get(freq, {})
        if not cal_idx_map:
            self.logger.error(f"No {freq} calendar available")
            return None

        indices = []
        missing_time_count = 0
        for item in kline_data:
            # 分钟K线数据必须含 time 字段；缺失时不能用 '00:00:00' 回退
            # （该时间戳不在交易日历里，会导致数据被静默丢弃）。
            time_val = item.get("time")
            if not time_val:
                missing_time_count += 1
                indices.append(None)
                continue
            ts = f"{item['date']} {time_val}"
            idx = cal_idx_map.get(ts)
            indices.append(idx)

        if missing_time_count > 0:
            self.logger.warning(
                f"{missing_time_count}/{len(kline_data)} 条分钟K线数据缺少 time 字段，已跳过"
            )

        valid_indices = [i for i in indices if i is not None]
        if not valid_indices:
            self.logger.warning(f"No valid timestamps in {freq} kline data")
            return None

        min_idx = min(valid_indices)
        max_idx = max(valid_indices)
        cal_len = max_idx - min_idx + 1

        field_arrays = {"_start_idx": min_idx}
        for field in QLIB_MIN_FIELDS:
            field_arrays[field] = np.full(cal_len, np.nan, dtype=np.float32)

        for i, (idx, item) in enumerate(zip(indices, kline_data)):
            if idx is None:
                continue
            pos = idx - min_idx
            if 0 <= pos < cal_len:
                for field in ["open", "high", "low", "close", "volume", "factor"]:
                    if field in item:
                        field_arrays[field][pos] = float(item[field])
                if "amount" in item and item.get("volume", 0) > 0:
                    field_arrays["vwap"][pos] = float(item["amount"]) / float(item["volume"])

        return field_arrays

    @staticmethod
    def _append_bin(bin_path: str, new_data: np.ndarray, data_start_idx: int):
        if not os.path.exists(bin_path):
            full_data = np.hstack([np.array([data_start_idx], dtype="<f"), new_data.astype("<f")])
            full_data.tofile(str(bin_path))
            return

        with open(bin_path, "rb") as f:
            raw = np.frombuffer(f.read(), dtype="<f")
        if len(raw) < 2:
            full_data = np.hstack([np.array([data_start_idx], dtype="<f"), new_data.astype("<f")])
            full_data.tofile(str(bin_path))
            return

        existing_start = int(raw[0])
        existing_data = raw[1:]
        existing_end = existing_start + len(existing_data) - 1
        new_end = data_start_idx + len(new_data) - 1

        if data_start_idx >= existing_start and new_end <= existing_end:
            return

        if data_start_idx > existing_end + 1:
            gap = data_start_idx - existing_end - 1
            nan_gap = np.full(gap, np.nan, dtype=np.float32)
            appended = np.hstack([existing_data, nan_gap, new_data.astype("<f")])
            data_start_idx = existing_start
        elif data_start_idx <= existing_start:
            if new_end < existing_start - 1:
                gap = existing_start - new_end - 1
                nan_gap = np.full(gap, np.nan, dtype=np.float32)
                appended = np.hstack([new_data.astype("<f"), nan_gap, existing_data])
            elif new_end < existing_start:
                appended = np.hstack([new_data.astype("<f"), existing_data])
            else:
                # 新数据覆盖旧数据开头，重叠区 [existing_start, min(existing_end, new_end)]
                # 同样：新数据非 NaN 才覆盖，保留旧有效值
                overlap_end_b = min(existing_end, new_end)
                overlap_len_b = overlap_end_b - existing_start + 1
                new_start_in_existing = existing_start - data_start_idx  # 新数据里对应 existing_start 的偏移
                new_overlap_b = new_data[new_start_in_existing:new_start_in_existing + overlap_len_b].astype("<f")
                old_overlap_b = existing_data[:overlap_len_b].astype("<f")
                merged_overlap_b = np.where(np.isnan(new_overlap_b), old_overlap_b, new_overlap_b)
                # 拼接：新数据 existing_start 之前的部分 + 合并后的重叠区
                appended = np.hstack([new_data[:new_start_in_existing].astype("<f"), merged_overlap_b])
                if new_end > existing_end:
                    appended = np.hstack([appended, new_data[new_start_in_existing + overlap_len_b:].astype("<f")])
                elif existing_end > new_end:
                    remaining = existing_data[overlap_len_b:]
                    appended = np.hstack([appended, remaining])
            data_start_idx = min(data_start_idx, existing_start)
        else:
            offset = data_start_idx - existing_start
            overlap_end = min(existing_end, new_end)
            overlap_offset = overlap_end - data_start_idx + 1
            merged = existing_data[:offset].copy()
            # 重叠区：新数据非 NaN 才覆盖旧数据，否则保留旧的有效值
            # （防止不完整的新数据用 NaN 覆盖已有数据，导致静默丢失）
            new_overlap = new_data[:overlap_offset].astype("<f")
            old_overlap = existing_data[offset:offset + overlap_offset].astype("<f")
            merged_overlap = np.where(np.isnan(new_overlap), old_overlap, new_overlap)
            merged = np.hstack([merged, merged_overlap])
            if new_end > existing_end:
                merged = np.hstack([merged, new_data[overlap_offset:].astype("<f")])
            elif existing_end > new_end:
                remaining = existing_data[overlap_end - existing_start + 1:]
                merged = np.hstack([merged, remaining])
            appended = merged
            data_start_idx = existing_start

        full_data = np.hstack([np.array([data_start_idx], dtype="<f"), appended.astype("<f")])
        full_data.tofile(str(bin_path))

    def check_local_coverage(self, code: str, field: str = "close", freq: str = "day", qlib_dir: Optional[str] = None, nan_aware: bool = False) -> Tuple[Optional[int], Optional[int]]:
        """检查本地数据覆盖范围。

        Args:
            nan_aware: True 时 end_idx 基于最后一个非 NaN 槽（而非文件末尾），
                       全 NaN 返回 (None, None)。用于检测被 NaN 拉长产生的伪覆盖
                       （如 1min 日历已扩展但数据未下载的场景）。默认 False 保持原行为。
        """
        qlib_dir = qlib_dir or self.code_to_qlib_dir(code)
        bin_path = os.path.join(self.features_dir, qlib_dir, f"{field}.{freq}.bin")
        if not os.path.exists(bin_path):
            return None, None
        with open(bin_path, "rb") as f:
            raw = np.frombuffer(f.read(), dtype="<f")
        if len(raw) < 2:
            return None, None
        start_idx_raw = raw[0]
        if np.isnan(start_idx_raw) or np.isinf(start_idx_raw) or abs(start_idx_raw) > 1e10:
            return None, None
        start_idx = int(start_idx_raw)
        if not nan_aware:
            end_idx = start_idx + len(raw[1:]) - 1
            return start_idx, end_idx
        # NaN-aware: end_idx 取最后一个非 NaN 槽；全 NaN 返回 None, None 触发重新下载
        body = raw[1:]
        valid_mask = ~np.isnan(body)
        if not np.any(valid_mask):
            return None, None
        end_idx = start_idx + int(np.nonzero(valid_mask)[0][-1])
        return start_idx, end_idx

    def get_missing_range(self, code: str, start_date: str, end_date: str) -> Optional[Tuple[str, str]]:
        start_idx = self.date_to_idx.get(start_date)
        end_idx = self.date_to_idx.get(end_date)
        if start_idx is None or end_idx is None:
            self.logger.warning(f"Date not in calendar: {start_date} or {end_date}")
            return None

        local_start, local_end = self.check_local_coverage(code)
        if local_start is not None and local_end is not None and local_end >= end_idx:
            return None

        if local_end is not None:
            fetch_start_idx = local_end + 1
            if fetch_start_idx < len(self.dates):
                fetch_start = self.dates[fetch_start_idx]
            else:
                return None
            if fetch_start > end_date:
                return None
        else:
            fetch_start = start_date

        return fetch_start, end_date
