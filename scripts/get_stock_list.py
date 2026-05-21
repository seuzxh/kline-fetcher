#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取 A 股完整历史股票列表

支持获取：
1. 当前所有A股（包括沪深京）
2. 退市股票
3. 新股

数据来源：akshare（免费开源）
"""

import os
import logging
from typing import List, Dict, Optional
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("stock_list_builder")


def get_all_stocks_with_akshare() -> pd.DataFrame:
    """
    使用 akshare 获取所有 A 股股票列表（当前 + 退市）
    
    返回:
        pd.DataFrame: 包含 code, name, market, list_date, delist_date
    """
    try:
        import akshare as ak
    except ImportError:
        logger.error("请先安装 akshare: pip install akshare")
        return pd.DataFrame()
    
    all_stocks = []
    
    # 1. 获取当前所有A股
    logger.info("正在获取当前A股列表...")
    try:
        current_df = ak.stock_info_a_code_name()
        if not current_df.empty:
            current_df['status'] = 'active'
            current_df['delist_date'] = None
            all_stocks.append(current_df)
            logger.info(f"  ✓ 获取到 {len(current_df)} 只当前A股")
    except Exception as e:
        logger.error(f"  ✗ 获取当前A股失败: {e}")
    
    # 2. 获取退市股票
    logger.info("正在获取退市股票列表...")
    try:
        delisted_df = ak.stock_zh_a_stop_em()
        if not delisted_df.empty:
            delisted_df['status'] = 'delisted'
            delisted_df['delist_date'] = delisted_df.get('退市日期', None)
            all_stocks.append(delisted_df)
            logger.info(f"  ✓ 获取到 {len(delisted_df)} 只退市股票")
    except Exception as e:
        logger.error(f"  ✗ 获取退市股票失败: {e}")
    
    # 3. 合并数据
    if not all_stocks:
        logger.error("未能获取任何股票数据")
        return pd.DataFrame()
    
    combined_df = pd.concat(all_stocks, ignore_index=True)
    
    # 4. 清理和标准化
    combined_df = combined_df.rename(columns={
        'code': 'code',
        'name': 'name'
    })
    
    # 5. 添加市场信息
    def infer_market(code):
        """从代码推断市场"""
        code_str = str(code)
        if code_str.startswith(('60', '68', '87')):
            return 'sh'  # 上海
        elif code_str.startswith(('00', '30')):
            return 'sz'  # 深圳
        elif code_str.startswith(('8', '4')):
            return 'bj'  # 北交所
        return 'unknown'
    
    combined_df['market'] = combined_df['code'].apply(infer_market)
    
    # 6. 添加 qlib 格式代码
    combined_df['qlib_code'] = combined_df.apply(
        lambda row: f"{row['market'].upper()}{row['code']}", axis=1
    )
    
    logger.info(f"共获取 {len(combined_df)} 只股票（当前: {len(current_df) if not current_df.empty else 0}, 退市: {len(delisted_df) if not delisted_df.empty else 0}）")
    
    return combined_df


def save_stock_list(df: pd.DataFrame, output_dir: str, format: str = 'both'):
    """
    保存股票列表到文件
    
    参数:
        df: 股票列表 DataFrame
        output_dir: 输出目录
        format: 保存格式 ('csv', 'txt', 'both')
    """
    os.makedirs(output_dir, exist_ok=True)
    
    if format in ('csv', 'both'):
        csv_path = os.path.join(output_dir, 'all_stocks.csv')
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        logger.info(f"✓ 已保存为 CSV: {csv_path}")
    
    if format in ('txt', 'both'):
        # 保存为 qlib instruments 格式
        txt_path = os.path.join(output_dir, 'all_stocks.txt')
        with open(txt_path, 'w', encoding='utf-8') as f:
            for _, row in df.iterrows():
                list_date = row.get('list_date', '1900-01-01') or '1900-01-01'
                delist_date = row.get('delist_date', '') or ''
                
                # qlib instruments 格式: code\tstart_date\tend_date
                f.write(f"{row['qlib_code']}\t{list_date}\t{delist_date}\n")
        logger.info(f"✓ 已保存为 TXT: {txt_path}")
    
    # 保存元信息
    meta_path = os.path.join(output_dir, 'stock_list_info.txt')
    with open(meta_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("A股完整历史股票列表\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"总股票数: {len(df)}\n")
        f.write(f"当前交易: {len(df[df['status'] == 'active'])}\n")
        f.write(f"已退市: {len(df[df['status'] == 'delisted'])}\n\n")
        f.write("市场分布:\n")
        f.write(df['market'].value_counts().to_string() + "\n\n")
        f.write("示例数据:\n")
        f.write(df.head(10).to_string())
    logger.info(f"✓ 已保存元信息: {meta_path}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="获取 A 股完整历史股票列表")
    parser.add_argument("--output-dir", default="./stock_lists", help="输出目录")
    parser.add_argument("--format", choices=['csv', 'txt', 'both'], default='both', help="保存格式")
    parser.add_argument("--no-akshare", action="store_true", help="不使用 akshare（使用备用方案）")
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("A 股完整历史股票列表获取工具")
    logger.info("=" * 60)
    
    # 获取股票列表
    if not args.no_akshare:
        df = get_all_stocks_with_akshare()
    else:
        logger.error("暂不支持备用方案，请安装 akshare: pip install akshare")
        return
    
    if df.empty:
        logger.error("未能获取股票数据")
        return
    
    # 保存结果
    save_stock_list(df, args.output_dir, args.format)
    
    # 显示统计信息
    logger.info("\n" + "=" * 60)
    logger.info("统计信息:")
    logger.info("=" * 60)
    logger.info(f"总股票数: {len(df)}")
    logger.info(f"当前交易: {len(df[df['status'] == 'active'])}")
    logger.info(f"已退市: {len(df[df['status'] == 'delisted'])}")
    logger.info(f"\n市场分布:")
    logger.info(df['market'].value_counts().to_string())
    logger.info("\n示例数据（前10行）:")
    print(df.head(10).to_string())
    
    logger.info("\n" + "=" * 60)
    logger.info(f"✓ 完成！文件已保存到: {args.output_dir}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
