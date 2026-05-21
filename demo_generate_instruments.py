#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演示如何生成 qlib 格式的 instruments 文件
"""

import os
import sys
import logging
from kline_fetcher.converter import KLineToQlib
from kline_fetcher.fetcher import KLineFetcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def load_stock_list_from_file(file_path: str) -> list:
    """从文件加载股票列表"""
    stocks = []
    if not os.path.exists(file_path):
        return stocks
        
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                code = parts[0]
                market = parts[1]
                qlib_code = parts[2]
                stocks.append((code, qlib_code, market))
    return stocks


def download_sample_data(stocks: list, start_date: str, end_date: str, qlib_data_dir: str = None):
    """下载一些样本数据用于演示"""
    from kline_fetcher.download import download_day_kline
    
    # 我们先创建一个临时的股池文件
    converter = KLineToQlib(qlib_data_dir=qlib_data_dir)
    temp_pool_path = os.path.join(converter.instruments_dir, "sample.txt")
    os.makedirs(converter.instruments_dir, exist_ok=True)
    
    with open(temp_pool_path, "w") as f:
        for code, qlib_code, market in stocks:
            f.write(f"{qlib_code}\t{start_date}\t{end_date}\n")
    
    print(f"正在下载样本数据: {len(stocks)} 只股票")
    download_day_kline(start_date, end_date, "sample", incremental=False, qlib_data_dir=qlib_data_dir)
    return temp_pool_path


def main():
    print("=" * 60)
    print("qlib instruments 文件生成演示")
    print("=" * 60)
    
    # 步骤 1: 初始化
    converter = KLineToQlib()
    
    # 检查是否有已下载的数据
    existing_stocks = converter.get_instruments_from_features()
    
    if existing_stocks:
        print(f"\n发现 {len(existing_stocks)} 只已下载的股票")
        print("\n正在生成 instruments 文件...")
        
        # 从已有数据生成 instruments
        file_path = converter.generate_instruments_file(existing_stocks, "all")
        
        print(f"\n✓ 成功生成 instruments 文件: {file_path}")
        
        # 显示文件内容预览
        print("\n文件内容预览:")
        with open(file_path, "r") as f:
            lines = f.readlines()
            for line in lines[:10]:  # 只显示前10行
                print(f"  {line.strip()}")
            if len(lines) > 10:
                print(f"  ... (共 {len(lines)} 行)")
    else:
        print("\n没有找到已下载的股票数据")
        print("\n要先生成 instruments 文件，您需要:")
        print("1. 下载一些股票数据")
        print("2. 然后运行这个脚本")
        
        # 提供示例
        print("\n或者，使用示例股票列表:")
        print("  - 运行: python -m kline_fetcher.download --start 2020-01-01 --end 2020-01-31 --pool all --generate-instruments")
        
        print("\n" + "=" * 60)
        print("说明:")
        print("- instruments 文件格式: 股票代码\\t起始日期\\t结束日期")
        print("- qlib 会根据这个文件知道每只股票的可用数据范围")
        print("- 不需要获取历史每天的市场股票，只要下载所有股票数据，然后自动生成 instruments")
        print("=" * 60)


if __name__ == "__main__":
    main()

